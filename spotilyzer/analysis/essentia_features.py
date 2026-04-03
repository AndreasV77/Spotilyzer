"""
Essentia-basierte Features — optional, Windows-native wenn verfügbar.

Essentia bietet gegenüber librosa:
  - BeatTracker mit höherer Präzision bei unregelmäßigen Rhythmen
  - Key-Detection mit Konfidenz-Score
  - Danceability-Algorithmus
  - Vortrainierte Mood/Genre-Classifier (essentia-tensorflow, separates Package)

Installation (Windows, wenn Build-Deps vorhanden):
  pip install essentia
  Benötigt: MSVC, CMake, Eigen3, libav, libsamplerate (via vcpkg o.ä.)

Solange Essentia nicht installiert ist, gibt dieses Modul None-Werte zurück.
Alle Aufrufer müssen None-Rückgaben tolerieren.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

try:
    import essentia.standard as _es
    _ESSENTIA_AVAILABLE = True
except ImportError:
    _ESSENTIA_AVAILABLE = False


def is_available() -> bool:
    """Gibt True zurück wenn Essentia installiert und importierbar ist."""
    return _ESSENTIA_AVAILABLE


def extract_key(audio: np.ndarray, sr: int) -> Optional[dict]:
    """
    Key-Detection via Essentia Key-Extractor.

    Vorteil gegenüber librosa: liefert Konfidenz-Score.

    Returns:
        {"key": "A", "scale": "minor", "confidence": 0.85}
        oder None wenn Essentia nicht verfügbar.
    """
    if not _ESSENTIA_AVAILABLE:
        return None
    try:
        es = _es
        # Essentia erwartet Mono Float32 bei sr=44100
        if sr != 44100:
            resampler = es.Resample(inputSampleRate=float(sr), outputSampleRate=44100.0)
            audio = resampler(audio.astype(np.float32))
        key_extractor = es.KeyExtractor()
        key, scale, confidence = key_extractor(audio.astype(np.float32))
        return {"key": key, "scale": scale, "confidence": round(float(confidence), 4)}
    except Exception:
        return None


def extract_danceability(audio: np.ndarray, sr: int) -> Optional[float]:
    """
    Danceability nach Essentia-Algorithmus (0.0–3.0, höher = tanzbarer).

    Returns:
        Float oder None wenn Essentia nicht verfügbar.
    """
    if not _ESSENTIA_AVAILABLE:
        return None
    try:
        es = _es
        if sr != 44100:
            resampler = es.Resample(inputSampleRate=float(sr), outputSampleRate=44100.0)
            audio = resampler(audio.astype(np.float32))
        danceability, _ = es.Danceability()(audio.astype(np.float32))
        return round(float(danceability), 4)
    except Exception:
        return None


def extract_rhythm_descriptors(audio: np.ndarray, sr: int) -> Optional[dict]:
    """
    Erweiterte Rhythmus-Deskriptoren via Essentia RhythmExtractor2013.

    Genauer als librosa bei unregelmäßigen Rhythmen (z.B. Swing, Rubato).

    Returns:
        {
            "bpm": 128.0,
            "bpm_confidence": 0.92,
            "beats": [0.23, 0.70, 1.17, ...],  # Beat-Positionen in Sekunden
            "bpm_estimates": [126.5, 128.0, 129.1],  # Kandidaten
        }
        oder None wenn Essentia nicht verfügbar.
    """
    if not _ESSENTIA_AVAILABLE:
        return None
    try:
        es = _es
        if sr != 44100:
            resampler = es.Resample(inputSampleRate=float(sr), outputSampleRate=44100.0)
            audio = resampler(audio.astype(np.float32))
        extractor = es.RhythmExtractor2013(method="multifeature")
        bpm, beats, confidence, _, bpm_estimates = extractor(audio.astype(np.float32))
        return {
            "bpm": round(float(bpm), 1),
            "bpm_confidence": round(float(confidence), 4),
            "beats": [round(float(b), 3) for b in beats],
            "bpm_estimates": [round(float(e), 1) for e in bpm_estimates],
        }
    except Exception:
        return None
