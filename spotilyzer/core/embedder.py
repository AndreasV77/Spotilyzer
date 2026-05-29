"""
MERTEmbedder - Singleton für MERT-v1-330M Audio-Embedding-Extraktion.

Extrahiert 1024-dimensionale Embeddings aus Audio-Dateien.
Unterstützt CUDA (GPU) und CPU mit automatischer Erkennung.

Quelle: Konsolidiert aus spotilyzer_gui.py (Z.71-128) und analyze_track.py (Z.43-111).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import numpy as np
import torch
import torchaudio
from transformers import AutoModel, AutoProcessor

from spotilyzer import MERT_MODEL_NAME, TARGET_SAMPLE_RATE, MERT_CHUNK_SEC
from spotilyzer.core._audio_loader import load_audio_file


class MERTEmbedder:
    """
    Singleton: Lädt MERT-v1-330M einmalig, extrahiert 1024-dim Embeddings.

    Usage:
        embedder = MERTEmbedder.get_instance(device="cuda")
        embedding = embedder.process_file(Path("track.mp3"))
    """

    _instance: Optional["MERTEmbedder"] = None

    def __init__(
        self,
        device: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialisiert den Embedder.

        Args:
            device: "cuda", "cpu" oder None (auto-detect).
            progress_callback: Optional, wird mit Status-Strings aufgerufen.
        """
        if device is None or device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self._notify = progress_callback or (lambda msg: None)

        self._notify("Lade MERT-Modell...")
        self.processor = AutoProcessor.from_pretrained(
            MERT_MODEL_NAME, trust_remote_code=True
        )
        self.model = AutoModel.from_pretrained(
            MERT_MODEL_NAME, trust_remote_code=True
        )
        self.model.to(self.device)
        self.model.eval()
        self._notify(f"MERT geladen auf {self.device.upper()}")

    @classmethod
    def get_instance(
        cls,
        device: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> "MERTEmbedder":
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
        """Stellt sicher dass das Modell auf dem richtigen Device ist (nach offload)."""
        current = next(self.model.parameters()).device
        if str(current) != self.device and not (
            self.device == "cuda" and str(current).startswith("cuda")
        ):
            self.model.to(self.device)

    def load_audio(self, filepath: Path) -> torch.Tensor:
        """
        Lädt eine Audio-Datei vollständig und preprocessed sie für MERT.

        - Konvertiert zu Mono
        - Resampled auf 24kHz
        - Kein Längen-Cap: der komplette Track wird zurückgegeben.
          Chunking erfolgt in process_file() via _chunk_waveform().

        Args:
            filepath: Pfad zur Audio-Datei.

        Returns:
            1D Tensor (Mono-Waveform bei 24kHz, volle Länge).

        Raises:
            RuntimeError: Wenn die Datei nicht geladen werden kann.
        """
        try:
            waveform, sample_rate = load_audio_file(filepath)
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Audio laden fehlgeschlagen: {filepath.name} - {e}")

        # Mono
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        # Resample auf Ziel-Samplerate
        if sample_rate != TARGET_SAMPLE_RATE:
            resampler = torchaudio.transforms.Resample(sample_rate, TARGET_SAMPLE_RATE)
            waveform = resampler(waveform)

        return waveform.squeeze(0)

    def _chunk_waveform(self, waveform: torch.Tensor) -> list[torch.Tensor]:
        """
        Teilt eine Waveform in überlappungsfreie MERT_CHUNK_SEC-Segmente auf.

        Der letzte Chunk wird mit Stille auf volle Chunk-Länge zero-gepaddet,
        damit MERT eine konsistente Eingabelänge erhält. Sehr kurze Endstücke
        (< 5 Sekunden) werden verworfen um Padding-Artefakte zu vermeiden.

        Args:
            waveform: 1D Tensor (Mono, 24kHz, beliebige Länge).

        Returns:
            Liste von Tensoren, jeder genau MERT_CHUNK_SEC * TARGET_SAMPLE_RATE Samples.
        """
        chunk_samples = TARGET_SAMPLE_RATE * MERT_CHUNK_SEC
        min_samples = TARGET_SAMPLE_RATE * 5  # Mindestlänge: 5 Sekunden
        total = waveform.shape[0]
        chunks: list[torch.Tensor] = []

        for start in range(0, total, chunk_samples):
            chunk = waveform[start : start + chunk_samples]
            if chunk.shape[0] < min_samples:
                break  # Zu kurzes Endstück verwerfen
            if chunk.shape[0] < chunk_samples:
                # Letzten Chunk auf volle Länge zero-padden
                pad = torch.zeros(chunk_samples - chunk.shape[0], dtype=chunk.dtype)
                chunk = torch.cat([chunk, pad])
            chunks.append(chunk)

        # Fallback: wenn der Track kürzer als min_samples ist (z.B. sehr kurze Clips)
        if not chunks:
            pad = torch.zeros(chunk_samples - waveform.shape[0], dtype=waveform.dtype)
            chunks.append(torch.cat([waveform, pad]))

        return chunks

    @torch.no_grad()
    def extract_embedding(self, waveform: torch.Tensor) -> np.ndarray:
        """
        Extrahiert ein 1024-dim Embedding aus einer Waveform.

        Args:
            waveform: 1D Tensor (Mono, 24kHz).

        Returns:
            1024-dimensionales numpy Array.

        Raises:
            RuntimeError: Bei Fehler in der Embedding-Extraktion.
        """
        try:
            inputs = self.processor(
                waveform.numpy(),
                sampling_rate=TARGET_SAMPLE_RATE,
                return_tensors="pt",
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            outputs = self.model(**inputs, output_hidden_states=True)
            embedding = outputs.last_hidden_state.mean(dim=1).squeeze(0)
            return embedding.cpu().numpy()
        except Exception as e:
            raise RuntimeError(f"Embedding-Extraktion fehlgeschlagen: {e}")

    def process_file(self, filepath: Path) -> np.ndarray:
        """
        Audio-Datei → 1024-dim Embedding (mean-pool über alle Chunks).
        Wird nur noch intern / für Tests genutzt.
        Für Inferenz: process_file_chunks().
        """
        self._ensure_on_device()
        waveform = self.load_audio(filepath)
        chunks = self._chunk_waveform(waveform)
        embeddings = [self.extract_embedding(chunk) for chunk in chunks]
        return np.mean(embeddings, axis=0)

    def process_file_chunks(self, filepath: Path) -> list[np.ndarray]:
        """
        Audio-Datei → Liste von 1024-dim Embeddings (ein Embedding pro 30s-Chunk).

        Kein mean-pooling: jeder Chunk wird einzeln ausgewertet.
        Das entspricht dem Trainings-Format (Deezer 30s-Previews = 1 Chunk = 1 Embedding).

        Args:
            filepath: Pfad zur Audio-Datei.

        Returns:
            Liste von 1024-dim numpy Arrays (mindestens 1 Element).

        Raises:
            RuntimeError: Bei Fehler in irgendeinem Schritt.
        """
        self._ensure_on_device()
        waveform = self.load_audio(filepath)
        chunks = self._chunk_waveform(waveform)
        return [self.extract_embedding(chunk) for chunk in chunks]
