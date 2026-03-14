"""
AudioInfo-Extraktion - Technische Metadaten aus Audio-Dateien.

Extrahiert: Duration, Sample-Rate, Channels, Bitrate, Format, Dateigröße,
BPM (Tempo), LUFS (Lautheit), Key (Tonart), Energy (spektral).

Nutzt ausschließlich torchaudio + torch (keine zusätzlichen Dependencies).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torchaudio

from spotilyzer.core._audio_loader import load_audio_file
from spotilyzer.data.models import AudioInfo


def extract_audio_info(filepath: Path) -> AudioInfo:
    """
    Extrahiert alle technischen Metadaten aus einer Audio-Datei.

    Args:
        filepath: Pfad zur Audio-Datei.

    Returns:
        AudioInfo-Dataclass mit allen verfügbaren Feldern.
    """
    path = Path(filepath)

    # Basis-Info via torchaudio.info() (schnell, kein Laden nötig)
    try:
        info = torchaudio.info(path)
        duration_sec = info.num_frames / info.sample_rate if info.sample_rate > 0 else 0.0
        sample_rate = info.sample_rate
        channels = info.num_channels
        # Bitrate: bits_per_sample * sample_rate * channels / 1000
        # Für komprimierte Formate (MP3) ist bits_per_sample oft 0
        if info.bits_per_sample > 0:
            bitrate = int(info.bits_per_sample * info.sample_rate * info.num_channels / 1000)
        else:
            # Schätze aus Dateigröße und Dauer
            if duration_sec > 0:
                bitrate = int(path.stat().st_size * 8 / duration_sec / 1000)
            else:
                bitrate = None
    except Exception:
        duration_sec = 0.0
        sample_rate = 0
        channels = 0
        bitrate = None

    # Datei-Metadaten
    file_size_bytes = path.stat().st_size if path.exists() else 0
    audio_format = path.suffix.lstrip(".").lower()

    # Audio laden für berechnete Metriken
    bpm = None
    lufs = None
    key = None
    energy = None

    try:
        waveform, sr = load_audio_file(path)

        # Mono für Analyse
        if waveform.shape[0] > 1:
            waveform_mono = waveform.mean(dim=0, keepdim=True)
        else:
            waveform_mono = waveform

        # BPM-Schätzung via Onset Detection
        bpm = _estimate_bpm(waveform_mono.squeeze(0), sr)

        # LUFS (vereinfachte Implementierung)
        lufs = _estimate_lufs(waveform, sr)

        # Key-Erkennung (Chroma-basiert)
        key = _estimate_key(waveform_mono.squeeze(0), sr)

        # Energie (RMS-basiert)
        energy = _estimate_energy(waveform_mono.squeeze(0))

    except Exception:
        pass  # Berechnete Metriken bleiben None

    return AudioInfo(
        duration_sec=duration_sec,
        sample_rate=sample_rate,
        channels=channels,
        bitrate=bitrate,
        format=audio_format,
        file_size_bytes=file_size_bytes,
        bpm=bpm,
        lufs=lufs,
        key=key,
        energy=energy,
    )


def _estimate_bpm(waveform: torch.Tensor, sample_rate: int) -> Optional[float]:
    """
    Schätzt BPM via Onset-Stärke und Autokorrelation.

    Vereinfachter Algorithmus:
    1. Spektrogramm berechnen
    2. Spectral Flux (Onset-Stärke) ableiten
    3. Autokorrelation für periodisches Tempo
    """
    try:
        # Hop size für ca. 100 FPS
        hop_length = max(sample_rate // 100, 1)

        # Spektrogramm
        spec_transform = torchaudio.transforms.Spectrogram(
            n_fft=2048, hop_length=hop_length, power=1.0
        )
        spec = spec_transform(waveform)

        # Spectral Flux (Onset-Stärke)
        flux = torch.diff(spec, dim=-1)
        flux = torch.clamp(flux, min=0)  # Nur positive Änderungen
        onset_strength = flux.sum(dim=0)  # Über Frequenzen summieren

        if onset_strength.shape[0] < 100:
            return None

        # Autokorrelation
        onset_np = onset_strength.numpy().astype(np.float64)
        onset_np -= onset_np.mean()
        if onset_np.std() < 1e-8:
            return None

        # Bereich: 40-240 BPM
        fps = sample_rate / hop_length
        min_lag = int(fps * 60 / 240)  # 240 BPM → kürzester Lag
        max_lag = int(fps * 60 / 40)   # 40 BPM → längster Lag

        if max_lag >= len(onset_np):
            max_lag = len(onset_np) - 1
        if min_lag >= max_lag:
            return None

        # Korrelation berechnen
        correlation = np.correlate(onset_np, onset_np, mode="full")
        correlation = correlation[len(onset_np) - 1:]  # Nur positive Lags

        # Besten Peak im BPM-Bereich finden
        search_region = correlation[min_lag:max_lag + 1]
        if len(search_region) == 0:
            return None

        best_lag = min_lag + int(np.argmax(search_region))

        if best_lag > 0:
            bpm = float(fps * 60 / best_lag)
            # Plausibilitätscheck
            if 40 <= bpm <= 240:
                return round(bpm, 1)

        return None
    except Exception:
        return None


def _estimate_lufs(waveform: torch.Tensor, sample_rate: int) -> Optional[float]:
    """
    Schätzt Integrated LUFS (vereinfachte EBU R128 Implementierung).

    Berechnet den RMS-Pegel und konvertiert in LUFS-Skala.
    Volle EBU R128 Implementierung würde K-Weighting und Gating erfordern.
    """
    try:
        # RMS über den gesamten Track
        rms = torch.sqrt(torch.mean(waveform ** 2))

        if rms < 1e-10:
            return -70.0  # Stille

        # dBFS
        db_fs = 20 * math.log10(float(rms))

        # Approximation: LUFS ≈ dBFS für normalisiertes Audio
        # (Echte LUFS braucht K-Weighting Filter, dies ist eine Annäherung)
        lufs = db_fs

        # Plausibilitätscheck
        if lufs < -70:
            lufs = -70.0

        return round(lufs, 1)
    except Exception:
        return None


def _estimate_key(waveform: torch.Tensor, sample_rate: int) -> Optional[str]:
    """
    Schätzt die Tonart via Chroma-Features.

    Verwendet den Krumhansl-Schmuckler Algorithmus:
    1. Chroma-Vektor berechnen (12 Tonklassen)
    2. Korrelation mit Major/Minor-Profilen
    3. Beste Übereinstimmung = geschätzte Tonart
    """
    try:
        # Krumhansl-Kessler Profile
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                                   2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                                   2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

        note_names = ["C", "C#", "D", "D#", "E", "F",
                       "F#", "G", "G#", "A", "A#", "B"]

        # Chroma via STFT
        n_fft = 4096
        hop_length = 2048

        # STFT
        window = torch.hann_window(n_fft)
        stft = torch.stft(
            waveform, n_fft=n_fft, hop_length=hop_length,
            window=window, return_complex=True
        )
        magnitudes = torch.abs(stft)

        # Frequenzen für jeden Bin
        freqs = torch.fft.rfftfreq(n_fft, d=1.0 / sample_rate)

        # Chroma-Akkumulation
        chroma = np.zeros(12)
        for i, freq in enumerate(freqs):
            freq_val = float(freq)
            if freq_val < 20 or freq_val > 5000:
                continue
            # MIDI-Note
            midi = 69 + 12 * math.log2(freq_val / 440.0)
            chroma_idx = int(round(midi)) % 12
            chroma[chroma_idx] += float(magnitudes[i].sum())

        if chroma.sum() < 1e-10:
            return None

        # Normalisieren
        chroma = chroma / chroma.sum()

        # Korrelation mit allen Rotationen der Major/Minor-Profile
        best_corr = -1.0
        best_key = "C major"

        for shift in range(12):
            rotated_major = np.roll(major_profile, shift)
            rotated_minor = np.roll(minor_profile, shift)

            corr_major = float(np.corrcoef(chroma, rotated_major)[0, 1])
            corr_minor = float(np.corrcoef(chroma, rotated_minor)[0, 1])

            if corr_major > best_corr:
                best_corr = corr_major
                best_key = f"{note_names[shift]} major"
            if corr_minor > best_corr:
                best_corr = corr_minor
                best_key = f"{note_names[shift]} minor"

        return best_key
    except Exception:
        return None


def _estimate_energy(waveform: torch.Tensor) -> Optional[float]:
    """
    Berechnet die normalisierte RMS-Energie (0.0 - 1.0).
    """
    try:
        rms = float(torch.sqrt(torch.mean(waveform ** 2)))
        # Normalisieren: typische Werte liegen zwischen 0.0 und 0.5
        # Wir skalieren so, dass 0.3 RMS ≈ 1.0 Energy ergibt
        energy = min(rms / 0.3, 1.0)
        return round(energy, 4)
    except Exception:
        return None


def extract_waveform_display(
    filepath: Path,
    target_width: int = 800,
) -> Optional[np.ndarray]:
    """
    Extrahiert eine downgesampelte Waveform für die Visualisierung.

    Args:
        filepath: Pfad zur Audio-Datei.
        target_width: Anzahl Datenpunkte (Pixel-Breite).

    Returns:
        2D numpy Array [2, target_width] mit Min/Max pro Spalte,
        oder None bei Fehler.
    """
    try:
        waveform, sr = load_audio_file(filepath)

        # Mono
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0)
        else:
            waveform = waveform.squeeze(0)

        samples = waveform.numpy()
        n_samples = len(samples)

        if n_samples < target_width:
            target_width = n_samples

        chunk_size = n_samples // target_width
        if chunk_size < 1:
            return None

        # Reshape und Min/Max pro Chunk
        trimmed = samples[: chunk_size * target_width]
        chunks = trimmed.reshape(target_width, chunk_size)

        mins = chunks.min(axis=1)
        maxs = chunks.max(axis=1)

        return np.array([mins, maxs])
    except Exception:
        return None
