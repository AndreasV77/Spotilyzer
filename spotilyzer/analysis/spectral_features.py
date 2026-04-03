"""
Spektral-Features (Tier 2A).

Alle Features werden aus dem STFT-Magnitude-Spektrogramm berechnet,
das einmalig berechnet und weitergereicht wird (kein doppeltes FFT).

Features:
    spectral_centroid   — Frequenz-Schwerpunkt in Hz (dunkel ↔ hell)
    spectral_bandwidth  — Spektrale Breite in Hz (schmal ↔ breit)
    spectral_rolloff    — 85%-Rolloff in Hz (Hochfrequenz-Abschnitt)
    spectral_flatness   — Tonalitätsgrad 0=tonal, 1=rauschartig
    spectral_contrast   — Mittlerer Peak-Valley-Kontrast in dB
    spectral_tilt       — Spektrale Neigung in dB/Oktave (negativ = basslastig)
    energy_sub/bass/mid/high — Energie-Anteile in 4 Frequenzbändern
"""

from __future__ import annotations

import numpy as np
import librosa

from .normalization import NormalizedFeature, normalize_feature


# ── Frequenzbänder ────────────────────────────────────────────────────────────
FREQUENCY_BANDS: dict[str, tuple[int, int]] = {
    "sub":  (20,    60),    # Sub-Bass
    "bass": (60,   250),    # Bass
    "mid":  (250, 4000),    # Mitten
    "high": (4000, 20000),  # Höhen
}


def extract_spectral_features(
    audio: np.ndarray, sr: int
) -> dict[str, NormalizedFeature]:
    """
    Extrahiert interpretierbare Spektral-Features aus einem Mono-Audio-Array.

    Args:
        audio: Mono float32 Array
        sr:    Sample-Rate in Hz

    Returns:
        Dict von Feature-Name → NormalizedFeature
    """
    results: dict[str, NormalizedFeature] = {}

    # STFT einmalig berechnen (n_fft=2048, hop=512 — librosa-Standard)
    S = np.abs(librosa.stft(audio))   # shape: (1025, n_frames)

    # ── Spectral Centroid ─────────────────────────────────────────────────────
    centroid = librosa.feature.spectral_centroid(S=S, sr=sr)
    results["spectral_centroid"] = normalize_feature(
        "spectral_centroid", float(np.mean(centroid)), "Hz"
    )

    # ── Spectral Bandwidth ────────────────────────────────────────────────────
    bandwidth = librosa.feature.spectral_bandwidth(S=S, sr=sr)
    results["spectral_bandwidth"] = normalize_feature(
        "spectral_bandwidth", float(np.mean(bandwidth)), "Hz"
    )

    # ── Spectral Rolloff (85%) ────────────────────────────────────────────────
    rolloff = librosa.feature.spectral_rolloff(S=S, sr=sr, roll_percent=0.85)
    results["spectral_rolloff"] = normalize_feature(
        "spectral_rolloff", float(np.mean(rolloff)), "Hz"
    )

    # ── Spectral Flatness ─────────────────────────────────────────────────────
    flatness = librosa.feature.spectral_flatness(S=S)
    results["spectral_flatness"] = normalize_feature(
        "spectral_flatness", round(float(np.mean(flatness)), 4), ""
    )

    # ── Spectral Contrast (7-Band-Mittelwert) ─────────────────────────────────
    contrast = librosa.feature.spectral_contrast(S=S, sr=sr)
    results["spectral_contrast"] = NormalizedFeature(
        name="spectral_contrast",
        raw_value=round(float(np.mean(contrast)), 2),
        unit="dB",
        normalized=None,
        category=None,
    )

    # ── Spectral Tilt (dB/Oktave) ─────────────────────────────────────────────
    tilt = _compute_spectral_tilt(S, sr)
    results["spectral_tilt"] = NormalizedFeature(
        name="spectral_tilt",
        raw_value=round(tilt, 3),
        unit="dB/oct",
        normalized=None,
        category=None,
    )

    # ── 4-Band Energy Distribution ────────────────────────────────────────────
    band_energies = _compute_band_energy(S, sr)
    for band_name, energy in band_energies.items():
        results[f"energy_{band_name}"] = NormalizedFeature(
            name=f"energy_{band_name}",
            raw_value=round(energy, 4),
            unit="ratio",
            normalized=round(energy, 4),  # bereits 0–1 (Anteil an Gesamtenergie)
            category=None,
        )

    return results


def _compute_spectral_tilt(S: np.ndarray, sr: int) -> float:
    """
    Linearer Fit über Log-Frequenz vs. mittlere Leistung in dB.

    Gibt die Steigung in dB/Oktave zurück:
        < 0 → mehr Energie in Tiefen (Bass-Heavy, Ambient, typisch)
        > 0 → mehr Energie in Höhen (selten, hell-schrill)

    Typische Werte: -3 bis -12 dB/oct für normale Musik.
    """
    n_fft = (S.shape[0] - 1) * 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    # Nur Frequenzen > 0 (DC-Anteil ausschließen)
    valid = freqs > 0
    freqs_valid = freqs[valid]

    mean_power = np.mean(S[valid] ** 2, axis=1)
    mean_power = np.maximum(mean_power, 1e-10)
    power_db = 10 * np.log10(mean_power)

    # Frequenz in Oktaven (log2)
    octaves = np.log2(freqs_valid)

    coeffs = np.polyfit(octaves, power_db, 1)
    return float(coeffs[0])


def _compute_band_energy(S: np.ndarray, sr: int) -> dict[str, float]:
    """
    Energie-Anteile in 4 Frequenzbändern, normalisiert auf Gesamtenergie.

    Returns:
        {"sub": 0.08, "bass": 0.22, "mid": 0.45, "high": 0.25}
        Summe ≈ 1.0 (ggf. Abweichungen durch Überlappung der Bandgrenzen)
    """
    n_fft = (S.shape[0] - 1) * 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    total_power = float(np.sum(S ** 2))
    if total_power < 1e-10:
        return {name: 0.0 for name in FREQUENCY_BANDS}

    result = {}
    for band_name, (f_low, f_high) in FREQUENCY_BANDS.items():
        mask = (freqs >= f_low) & (freqs < f_high)
        band_power = float(np.sum(S[mask] ** 2))
        result[band_name] = band_power / total_power

    return result
