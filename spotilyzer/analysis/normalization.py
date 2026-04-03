"""
Normalisierung und Kategorisierung von Audio-Features.

NormalizedFeature: Rohwert + normalisierter Wert (0–1) + semantische Kategorie.
CATEGORY_THRESHOLDS: Feste Schwellwerte für interpretierbare Kategorien.
NORMALIZATION_RANGES: Min/Max für lineare Normalisierung auf 0–1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class NormalizedFeature:
    """Feature mit allen Normalisierungsebenen."""

    name: str
    raw_value: float
    unit: str
    normalized: Optional[float]  # 0.0–1.0, None wenn kein Range definiert
    category: Optional[str]      # "very_low"|"low"|"medium"|"high"|"very_high"

    def to_dict(self) -> dict:
        d: dict = {"value": self.raw_value, "unit": self.unit}
        if self.normalized is not None:
            d["normalized"] = self.normalized
        if self.category is not None:
            d["category"] = self.category
        return d


# ── Kategorie-Schwellwerte ────────────────────────────────────────────────────
# Format: list[(upper_bound_exclusive, category_label)]
# Letztes Element muss upper_bound=inf haben.

CATEGORY_THRESHOLDS: dict[str, list[tuple[float, str]]] = {
    # Spektral
    "spectral_centroid": [
        (1500, "very_low"), (2500, "low"), (3500, "medium"),
        (5000, "high"), (float("inf"), "very_high"),
    ],
    "spectral_bandwidth": [
        (1000, "very_low"), (2000, "low"), (3000, "medium"),
        (4500, "high"), (float("inf"), "very_high"),
    ],
    "spectral_rolloff": [
        (2000, "very_low"), (4000, "low"), (7000, "medium"),
        (12000, "high"), (float("inf"), "very_high"),
    ],
    "spectral_flatness": [
        (0.02, "very_low"), (0.1, "low"), (0.3, "medium"),
        (0.6, "high"), (float("inf"), "very_high"),
    ],
    # Temporal
    "onset_rate": [
        (1.5, "very_low"), (4.0, "low"), (8.0, "medium"),
        (14.0, "high"), (float("inf"), "very_high"),
    ],
    "tempo_stability": [
        (0.3, "very_low"), (0.5, "low"), (0.7, "medium"),
        (0.85, "high"), (float("inf"), "very_high"),
    ],
    "beat_strength": [
        (0.2, "very_low"), (0.4, "low"), (0.6, "medium"),
        (0.8, "high"), (float("inf"), "very_high"),
    ],
    "hpss_ratio": [
        (0.3, "very_low"), (0.7, "low"), (1.3, "medium"),
        (2.5, "high"), (float("inf"), "very_high"),
    ],
    # Produktion
    "dynamic_range_db": [
        (4.0, "very_low"), (8.0, "low"), (14.0, "medium"),
        (20.0, "high"), (float("inf"), "very_high"),
    ],
    "crest_factor": [
        (3.0, "very_low"), (6.0, "low"), (10.0, "medium"),
        (15.0, "high"), (float("inf"), "very_high"),
    ],
    "stereo_width": [
        (0.2, "very_low"), (0.4, "low"), (0.65, "medium"),
        (0.85, "high"), (float("inf"), "very_high"),
    ],
}

# ── Normalisierungs-Ranges (min, max) für lineare 0–1 Skalierung ─────────────
NORMALIZATION_RANGES: dict[str, tuple[float, float]] = {
    "spectral_centroid":   (500.0,  8000.0),
    "spectral_bandwidth":  (200.0,  6000.0),
    "spectral_rolloff":    (500.0, 18000.0),
    "spectral_flatness":   (0.0,    1.0),
    "onset_rate":          (0.0,   20.0),
    "tempo_stability":     (0.0,    1.0),
    "beat_strength":       (0.0,    1.0),
    "hpss_ratio":          (0.0,    5.0),
    "dynamic_range_db":    (0.0,   30.0),
    "crest_factor":        (1.0,   25.0),
    "stereo_width":        (0.0,    1.0),
}


def normalize_feature(name: str, raw_value: float, unit: str) -> NormalizedFeature:
    """
    Normalisiert ein Feature auf Kategorie und 0–1-Wert.

    Args:
        name:      Feature-Schlüssel (muss in CATEGORY_THRESHOLDS / NORMALIZATION_RANGES stehen)
        raw_value: Rohwert in natürlichen Einheiten
        unit:      Einheit als String (nur für Anzeige)

    Returns:
        NormalizedFeature mit allen Ebenen ausgefüllt
    """
    # Lineare Normalisierung 0–1
    normalized: Optional[float] = None
    if name in NORMALIZATION_RANGES:
        lo, hi = NORMALIZATION_RANGES[name]
        if hi > lo:
            normalized = round(max(0.0, min(1.0, (raw_value - lo) / (hi - lo))), 4)

    # Kategorie via Threshold-Liste
    category: Optional[str] = None
    if name in CATEGORY_THRESHOLDS:
        for upper, cat in CATEGORY_THRESHOLDS[name]:
            if raw_value <= upper:
                category = cat
                break

    return NormalizedFeature(
        name=name,
        raw_value=raw_value,
        unit=unit,
        normalized=normalized,
        category=category,
    )
