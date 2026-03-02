"""
MERTEmbedder - Singleton für MERT-v1-95M Audio-Embedding-Extraktion.

Extrahiert 768-dimensionale Embeddings aus Audio-Dateien.
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

from spotilyzer import MERT_MODEL_NAME, TARGET_SAMPLE_RATE, MAX_AUDIO_LENGTH_SEC


class MERTEmbedder:
    """
    Singleton: Lädt MERT-v1-95M einmalig, extrahiert 768-dim Embeddings.

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

    def load_audio(self, filepath: Path) -> torch.Tensor:
        """
        Lädt eine Audio-Datei und preprocessed sie für MERT.

        - Konvertiert zu Mono
        - Resampled auf 24kHz
        - Beschneidet auf max. 30 Sekunden (Mitte des Tracks)

        Args:
            filepath: Pfad zur Audio-Datei.

        Returns:
            1D Tensor (Mono-Waveform bei 24kHz).

        Raises:
            RuntimeError: Wenn die Datei nicht geladen werden kann.
        """
        try:
            waveform, sample_rate = torchaudio.load(filepath)
        except Exception as e:
            raise RuntimeError(f"Audio laden fehlgeschlagen: {filepath.name} - {e}")

        # Mono
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        # Resample auf Ziel-Samplerate
        if sample_rate != TARGET_SAMPLE_RATE:
            resampler = torchaudio.transforms.Resample(sample_rate, TARGET_SAMPLE_RATE)
            waveform = resampler(waveform)

        # Max. Länge beschneiden (Mitte des Tracks)
        max_samples = TARGET_SAMPLE_RATE * MAX_AUDIO_LENGTH_SEC
        if waveform.shape[1] > max_samples:
            start = (waveform.shape[1] - max_samples) // 2
            waveform = waveform[:, start : start + max_samples]

        return waveform.squeeze(0)

    @torch.no_grad()
    def extract_embedding(self, waveform: torch.Tensor) -> np.ndarray:
        """
        Extrahiert ein 768-dim Embedding aus einer Waveform.

        Args:
            waveform: 1D Tensor (Mono, 24kHz).

        Returns:
            768-dimensionales numpy Array.

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
        Komplette Pipeline: Audio-Datei → 768-dim Embedding.

        Args:
            filepath: Pfad zur Audio-Datei.

        Returns:
            768-dimensionales numpy Array.

        Raises:
            RuntimeError: Bei Fehler in irgendeinem Schritt.
        """
        waveform = self.load_audio(filepath)
        return self.extract_embedding(waveform)
