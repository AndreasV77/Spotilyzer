"""
Produktions-Features (Tier 2A).

Features:
    stereo_width     — L-R-Unkorrelation: 0=mono, 1=maximale Breite
    mid_side_ratio   — Verhältnis Mid- zu Side-Energie (hoch = eher mono)
    dynamic_range_db — Peak − RMS in dB (hoch = dynamischer Mix)
    crest_factor     — Peak / RMS (hoch = viele Transienten, geringe Kompression)
    lufs             — Integrated Loudness nach EBU R128 in dBFS
    clipping_ratio   — Anteil geclippter Samples (≥ 0.999) an Gesamt-Samples
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from .normalization import NormalizedFeature, normalize_feature


def extract_production_features(
    audio: np.ndarray, sr: int
) -> dict[str, NormalizedFeature]:
    """
    Extrahiert produktionsbezogene Features.

    Args:
        audio: Stereo oder Mono. Shape: (channels, samples) oder (samples,).
        sr:    Sample-Rate in Hz

    Returns:
        Dict von Feature-Name → NormalizedFeature
    """
    results: dict[str, NormalizedFeature] = {}

    # ── Kanal-Normalisierung ─────────────────────────────────────────────────
    if audio.ndim == 1:
        left = right = mono = audio
        is_stereo = False
    elif audio.shape[0] == 1:
        left = right = mono = audio[0]
        is_stereo = False
    else:
        left = audio[0]
        right = audio[1]
        mono = (left + right) / 2
        is_stereo = True

    # ── Stereo Width ─────────────────────────────────────────────────────────
    if is_stereo:
        corr = float(np.corrcoef(left, right)[0, 1])
        # corr=1 → vollständig mono; corr=0 → unkorrreliert; corr<0 → phasenverdreht
        stereo_width = max(0.0, 1.0 - abs(corr))
        results["stereo_width"] = normalize_feature(
            "stereo_width", round(stereo_width, 4), ""
        )

        # ── Mid/Side Ratio ────────────────────────────────────────────────────
        mid = (left + right) / 2
        side = (left - right) / 2
        mid_energy = float(np.sum(mid ** 2))
        side_energy = float(np.sum(side ** 2))
        ms_ratio = mid_energy / (side_energy + 1e-10)
        results["mid_side_ratio"] = NormalizedFeature(
            name="mid_side_ratio",
            raw_value=round(ms_ratio, 3),
            unit="M/S",
            normalized=None,
            category=None,
        )
    else:
        results["stereo_width"] = normalize_feature("stereo_width", 0.0, "")
        results["mid_side_ratio"] = NormalizedFeature(
            name="mid_side_ratio", raw_value=0.0, unit="M/S",
            normalized=None, category=None,
        )

    # ── Dynamic Range (Peak − RMS in dB) ────────────────────────────────────
    peak = float(np.max(np.abs(mono)))
    rms = float(np.sqrt(np.mean(mono ** 2)))

    if rms > 1e-10 and peak > 1e-10:
        dynamic_range_db = 20 * math.log10(peak / rms)
        results["dynamic_range_db"] = normalize_feature(
            "dynamic_range_db", round(dynamic_range_db, 2), "dB"
        )

        # ── Crest Factor ──────────────────────────────────────────────────────
        crest_factor = peak / rms
        results["crest_factor"] = normalize_feature(
            "crest_factor", round(crest_factor, 3), ""
        )

    # ── Clipping Ratio ────────────────────────────────────────────────────────
    clipping = float(np.sum(np.abs(mono) >= 0.999)) / max(len(mono), 1)
    results["clipping_ratio"] = NormalizedFeature(
        name="clipping_ratio",
        raw_value=round(clipping, 6),
        unit="",
        normalized=round(clipping, 6),
        category="very_high" if clipping > 0.01 else ("low" if clipping > 0.001 else "very_low"),
    )

    # ── LUFS (EBU R128 via pyloudnorm) ────────────────────────────────────────
    lufs = _estimate_lufs(audio, sr)
    if lufs is not None:
        results["lufs"] = NormalizedFeature(
            name="lufs",
            raw_value=round(lufs, 1),
            unit="dBFS",
            normalized=None,
            category=None,
        )

    return results


def _estimate_lufs(audio: np.ndarray, sr: int) -> Optional[float]:
    """LUFS Integrated Loudness nach EBU R128 via pyloudnorm."""
    try:
        import pyloudnorm as pyln

        if audio.ndim == 1:
            data = audio[:, np.newaxis].astype(np.float64)
        elif audio.shape[0] <= 2:
            data = audio.T.astype(np.float64)   # (samples, channels)
        else:
            data = audio.astype(np.float64)

        meter = pyln.Meter(sr)
        lufs = meter.integrated_loudness(data)
        return float(lufs) if np.isfinite(lufs) else None
    except Exception:
        return None
