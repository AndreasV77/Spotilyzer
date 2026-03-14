"""
CLAPAnalyzer - Singleton für LAION CLAP Zero-Shot Audio-Text-Klassifikation.

Nutzt laion/larger_clap_music für Genre/Mood-Ähnlichkeitsanalyse ohne Training.
Audio wird gegen konfigurierbare Text-Tags verglichen (Cosine Similarity).

Usage:
    analyzer = CLAPAnalyzer.get_instance(device="cuda")
    result = analyzer.analyze(Path("track.mp3"))
    print(result.top_genre())   # z.B. "metal"
    print(result.genre_scores)  # {"metal": 0.42, "rock": 0.21, ...}
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import numpy as np
import torch
import torchaudio
from transformers import ClapModel, ClapProcessor

from spotilyzer import CLAP_MODEL_NAME
from spotilyzer.core._audio_loader import load_audio_file
from spotilyzer.data.models import CLAPResult


# Standard-Tag-Sets (konfigurierbar, nicht hardcoded)
DEFAULT_TAG_SETS: dict[str, list[str]] = {
    "genre": [
        "metal",
        "hard rock",
        "rock",
        "pop",
        "electronic",
        "hip-hop",
        "r&b",
        "jazz",
        "classical",
        "country",
        "folk",
        "reggae",
        "punk",
        "alternative",
        "indie",
        "dance",
        "ambient",
        "soul",
    ],
    "mood": [
        "aggressive",
        "melancholic",
        "upbeat",
        "dark",
        "euphoric",
        "calm",
        "energetic",
        "romantic",
        "angry",
        "sad",
        "happy",
        "tense",
        "relaxed",
        "epic",
        "playful",
    ],
}

# Anzahl der Top-Tags die in CLAPResult.top_tags gespeichert werden
TOP_N_TAGS = 5


class CLAPAnalyzer:
    """
    Singleton: Lädt LAION CLAP einmalig, analysiert Audio via Zero-Shot Text-Matching.

    VRAM-Verbrauch: ~600 MB (trivial, passt auch parallel zu MERT auf 6 GB).

    Usage:
        analyzer = CLAPAnalyzer.get_instance(device="cuda")
        result = analyzer.analyze(Path("track.mp3"))

        # Mit eigenen Tag-Sets:
        result = analyzer.analyze(Path("track.mp3"), tag_sets={
            "genre": ["metal", "pop", "jazz"],
            "energy": ["calm", "energetic", "intense"],
        })
    """

    _instance: Optional["CLAPAnalyzer"] = None

    def __init__(
        self,
        device: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        if device is None or device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self._notify = progress_callback or (lambda msg: None)

        self._notify("Lade CLAP-Modell...")
        self.processor = ClapProcessor.from_pretrained(CLAP_MODEL_NAME)
        self.model = ClapModel.from_pretrained(CLAP_MODEL_NAME)
        self.model.to(self.device)
        self.model.eval()
        self._notify(f"CLAP geladen auf {self.device.upper()}")

    @classmethod
    def get_instance(
        cls,
        device: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> "CLAPAnalyzer":
        """Gibt die Singleton-Instanz zurück (erstellt sie bei Bedarf)."""
        if cls._instance is None:
            cls._instance = cls(device=device, progress_callback=progress_callback)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Setzt die Singleton-Instanz zurück (für Tests)."""
        cls._instance = None

    def offload_to_cpu(self) -> None:
        """
        Verschiebt Modell auf CPU und leert GPU-Cache.
        Für sequentiellen VRAM-Modus (MERT + CLAP abwechselnd).
        """
        self.model.to("cpu")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def restore_to_device(self) -> None:
        """Verschiebt Modell zurück auf das konfigurierte Device."""
        self.model.to(self.device)

    def _ensure_on_device(self) -> None:
        """Stellt sicher dass das Modell auf dem richtigen Device ist."""
        current = next(self.model.parameters()).device
        if str(current) != self.device and not (
            self.device == "cuda" and str(current).startswith("cuda")
        ):
            self.model.to(self.device)

    def _load_audio(self, audio_path: Path) -> tuple[np.ndarray, int]:
        """
        Lädt Audio-Datei als Mono-Numpy-Array.

        Returns:
            (waveform_numpy, sample_rate) — CLAP-Processor übernimmt Resampling.
        """
        try:
            waveform, sr = load_audio_file(audio_path)
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Audio laden fehlgeschlagen: {audio_path.name} — {e}")

        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        return waveform.squeeze(0).numpy(), sr

    @torch.no_grad()
    def _get_audio_embedding(self, waveform: np.ndarray, sr: int) -> torch.Tensor:
        """
        Berechnet das normalisierte Audio-Embedding via CLAP.

        Returns:
            Tensor [1, 512] (L2-normalisiert).
        """
        inputs = self.processor(
            audio=waveform,
            sampling_rate=sr,
            return_tensors="pt",
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        audio_embed = self.model.get_audio_features(**inputs)
        if not isinstance(audio_embed, torch.Tensor):
            audio_embed = audio_embed.pooler_output
        return audio_embed / audio_embed.norm(dim=-1, keepdim=True)

    @torch.no_grad()
    def _get_text_embeddings(self, tags: list[str]) -> torch.Tensor:
        """
        Berechnet normalisierte Text-Embeddings für eine Liste von Tags.

        Returns:
            Tensor [N, 512] (L2-normalisiert).
        """
        inputs = self.processor(
            text=tags,
            return_tensors="pt",
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        text_embeds = self.model.get_text_features(**inputs)
        if not isinstance(text_embeds, torch.Tensor):
            text_embeds = text_embeds.pooler_output
        return text_embeds / text_embeds.norm(dim=-1, keepdim=True)

    def analyze(
        self,
        audio_path: Path,
        tag_sets: Optional[dict[str, list[str]]] = None,
    ) -> CLAPResult:
        """
        Zero-Shot Genre/Mood-Analyse via CLAP.

        Args:
            audio_path: Pfad zur Audio-Datei.
            tag_sets: Tag-Sets für die Klassifikation. Default: DEFAULT_TAG_SETS.
                      Format: {"set_name": ["tag1", "tag2", ...]}

        Returns:
            CLAPResult mit Cosine-Similarity-Scores pro Tag-Set und Top-Tags.

        Raises:
            RuntimeError: Bei Fehler in Audio-Lade oder Inference.
        """
        if tag_sets is None:
            tag_sets = DEFAULT_TAG_SETS

        self._ensure_on_device()

        # Audio laden und Embedding berechnen
        waveform, sr = self._load_audio(audio_path)
        audio_embed = self._get_audio_embedding(waveform, sr)

        # Pro Tag-Set: Cosine-Similarity berechnen
        result_scores: dict[str, dict[str, float]] = {}
        all_scores: dict[str, float] = {}

        for set_name, tags in tag_sets.items():
            if not tags:
                continue
            text_embeds = self._get_text_embeddings(tags)
            # Cosine Similarity: audio [1,512] @ text [N,512].T → [1,N]
            similarities = (audio_embed @ text_embeds.T).squeeze(0).cpu().numpy()
            scores = {tag: float(sim) for tag, sim in zip(tags, similarities)}
            result_scores[set_name] = scores
            all_scores.update(scores)

        # Top-N Tags über alle Sets nach Similarity sortiert
        top_tags = sorted(all_scores, key=all_scores.__getitem__, reverse=True)[:TOP_N_TAGS]

        return CLAPResult(
            tag_scores=result_scores,
            top_tags=top_tags,
        )
