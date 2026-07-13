"""
CLAPAnalyzer - Singleton für LAION CLAP Zero-Shot Audio-Text-Klassifikation.

Nutzt laion/clap-htsat-fused für Genre/Mood-Ähnlichkeitsanalyse ohne Training.
(laion/larger_clap_music wurde verworfen: defekte HF-Konvertierung, siehe CLAUDE.md.)
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

from spotilyzer import CLAP_MODEL_NAME, CLAP_CHUNK_SEC
from spotilyzer.core._audio_loader import load_audio_file
from spotilyzer.data.models import CLAPResult


# Standard-Tag-Sets (konfigurierbar, nicht hardcoded)
DEFAULT_TAG_SETS: dict[str, list[str]] = {
    "genre": [
        "gothic metal",
        "doom metal",
        "symphonic metal",
        "black metal",
        "death metal",
        "metalcore",
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
        "haunting",
        "atmospheric",
        "ethereal",
        "powerful",
        "brooding",
        "heavy",
        "intense",
        "dreamy",
        "nostalgic",
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

    # ClapFeatureExtractor validates sample rate and raises ValueError if it
    # doesn't match — it does NOT resample silently.
    CLAP_SAMPLE_RATE = 48_000

    def _load_audio(self, audio_path: Path) -> tuple[np.ndarray, int]:
        """
        Lädt Audio-Datei vollständig als Mono-Numpy-Array, resampled auf 48 kHz.

        ClapFeatureExtractor erwartet exakt 48 kHz und resampled nicht selbst —
        es wirft einen ValueError bei abweichender Rate. Daher resampling hier.

        Returns:
            (waveform_numpy, 48000)
        """
        try:
            waveform, sr = load_audio_file(audio_path)
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Audio laden fehlgeschlagen: {audio_path.name} — {e}")

        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        if sr != self.CLAP_SAMPLE_RATE:
            resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=self.CLAP_SAMPLE_RATE)
            waveform = resampler(waveform)
            sr = self.CLAP_SAMPLE_RATE

        return waveform.squeeze(0).numpy(), sr

    def _chunk_waveform(self, waveform: np.ndarray, sr: int) -> list[np.ndarray]:
        """
        Teilt eine Waveform in CLAP_CHUNK_SEC-Segmente auf.

        ClapProcessor trunciert intern auf sein natives Fenster (10s @ 48kHz).
        Durch explizites Chunking stellen wir sicher, dass der gesamte Track
        analysiert wird — nicht nur die ersten 10 Sekunden.

        Sehr kurze Endstücke (< 3 Sekunden) werden verworfen.

        Args:
            waveform: 1D numpy float32 Array (Mono, native sample rate).
            sr: Sample-Rate der Waveform.

        Returns:
            Liste von numpy Arrays, jeder max. CLAP_CHUNK_SEC Sekunden lang.
        """
        chunk_samples = sr * CLAP_CHUNK_SEC
        min_samples = sr * 3  # Mindestlänge: 3 Sekunden
        total = len(waveform)
        chunks: list[np.ndarray] = []

        for start in range(0, total, chunk_samples):
            chunk = waveform[start : start + chunk_samples]
            if len(chunk) >= min_samples:
                chunks.append(chunk)

        return chunks or [waveform]  # Fallback für sehr kurze Tracks

    @torch.no_grad()
    def _get_scores_for_tags(
        self, waveform: np.ndarray, sr: int, tags: list[str]
    ) -> np.ndarray:
        """
        Berechnet CLAP-Ähnlichkeits-Scores für Audio gegen eine Tag-Liste.

        Nutzt model(**inputs) full-forward (stabiles API in transformers 5.x).

        Returns:
            numpy Array [N] mit logit_per_audio Scores (skalierte Cosine-Sim).
        """
        inputs = self.processor(
            audio=waveform,
            text=tags,
            sampling_rate=sr,
            return_tensors="pt",
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        outputs = self.model(**inputs)
        # logits_per_audio: [1, N_tags] — audio-to-text similarity (scaled)
        return outputs.logits_per_audio.squeeze(0).cpu().numpy()

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

        # Audio laden (vollständiger Track, kein Cap)
        waveform, sr = self._load_audio(audio_path)
        chunks = self._chunk_waveform(waveform, sr)

        # Pro Tag-Set: Scores über alle Chunks mitteln
        result_scores: dict[str, dict[str, float]] = {}
        all_scores: dict[str, float] = {}

        for set_name, tags in tag_sets.items():
            if not tags:
                continue

            # Scores pro Chunk sammeln, dann arithmetisch mitteln
            chunk_scores: list[np.ndarray] = []
            for chunk in chunks:
                chunk_scores.append(self._get_scores_for_tags(chunk, sr, tags))
            scores_arr = np.mean(chunk_scores, axis=0)

            scores = {tag: float(s) for tag, s in zip(tags, scores_arr)}
            result_scores[set_name] = scores
            all_scores.update(scores)

        # Top-N Tags über alle Sets nach Score sortiert
        top_tags = sorted(all_scores, key=all_scores.__getitem__, reverse=True)[:TOP_N_TAGS]

        return CLAPResult(
            tag_scores=result_scores,
            top_tags=top_tags,
        )
