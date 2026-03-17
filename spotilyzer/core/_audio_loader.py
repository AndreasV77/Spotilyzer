"""
Robuste Audio-Lade-Hilfsfunktion.

Nutzt soundfile direkt statt torchaudio.load(), da torchaudio >= 2.10
den backend-Parameter ignoriert und immer torchcodec verwendet.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch


def load_audio_file(filepath: Path) -> tuple[torch.Tensor, int]:
    """
    Lädt eine Audio-Datei als Tensor.

    Nutzt soundfile (WAV, FLAC, OGG, MP3, AIFF, ...).
    Für M4A/AAC/WMA fällt es auf torchaudio zurück (benötigt torchcodec).

    Returns:
        (waveform, sample_rate) — waveform shape: [channels, samples], float32.

    Raises:
        RuntimeError: Wenn die Datei nicht geladen werden kann.
    """
    try:
        import soundfile as sf
        data, sr = sf.read(str(filepath), dtype="float32", always_2d=True)
        # soundfile: (samples, channels) → torch: (channels, samples)
        waveform = torch.from_numpy(np.ascontiguousarray(data.T))
        return waveform, sr
    except Exception as sf_err:
        # Fallback für Formate die soundfile nicht unterstützt (M4A, AAC, WMA)
        try:
            import torchaudio
            waveform, sr = torchaudio.load(str(filepath))
            return waveform, sr
        except Exception as ta_err:
            raise RuntimeError(
                f"Audio laden fehlgeschlagen: {Path(filepath).name} "
                f"(soundfile: {sf_err} | torchaudio: {ta_err})"
            )
