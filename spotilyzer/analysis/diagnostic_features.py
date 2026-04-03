"""
Mix-Diagnose Features (Phase 2, Tier 2B).

Identifiziert klangliche Probleme und Stärken in der Frequenzverteilung.

7-Band-Spektrum (Anteile an Gesamtenergie):
    sub_bass   20–60 Hz    — Fundament, Rumble, Kick-Tiefe
    bass       60–250 Hz   — Bass-Körper, Kick-Punch
    low_mid   250–600 Hz   — Wärme / Matsch-Zone
    mid       600–2500 Hz  — Präsenz, Vokal-Körper, Piano
    high_mid  2500–6000 Hz — Klarheit / Schärfe-Zone
    high      6000–12000 Hz — Glanz, Detail
    ultra_high 12–20 kHz   — Luft, subtile Obertöne

Abgeleitete Diagnose-Scores (0–1, basierend auf Referenz-Spektrum):
    boominess      — Überbetonung Bass-Region (60–250 Hz)
    muddiness      — Überbetonung Matsch-Zone (250–600 Hz)
    harshness      — Überbetonung Schärfe-Zone (2500–6000 Hz)
    brightness     — Glanz-Anteil (6–12 kHz)
    air            — Luft-Anteil (12–20 kHz)
    mix_balance    — Ähnlichkeit zur Referenz-Spektrum (1.0 = ideal)

mix_issues:
    Liste erkannter Probleme als Strings — direkt KI-lesbar.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import librosa

from .normalization import NormalizedFeature, normalize_feature


# ── Frequenzbänder ────────────────────────────────────────────────────────────

DIAGNOSTIC_BANDS: dict[str, tuple[int, int]] = {
    "sub_bass":    (20,    60),
    "bass":        (60,   250),
    "low_mid":     (250,  600),
    "mid":         (600, 2500),
    "high_mid":   (2500, 6000),
    "high":       (6000, 12000),
    "ultra_high": (12000, 20000),
}

# Referenz-Spektrum: typische Verteilung ausgewogener kommerzieller Musik
# (empirisch, Pop/Rock/Electronic, EBU-normalisiert ca. −14 LUFS)
REFERENCE_SPECTRUM: dict[str, float] = {
    "sub_bass":   0.04,
    "bass":       0.22,
    "low_mid":    0.14,
    "mid":        0.28,
    "high_mid":   0.16,
    "high":       0.11,
    "ultra_high": 0.05,
}

# Schwellwerte für Diagnose-Kategorien (Energie-Anteile, 0–1)
# "medium" = gesunder Bereich; "high/very_high" = potenzielles Problem (Überbetonung)
_BAND_THRESHOLDS: dict[str, list[tuple[float, str]]] = {
    "sub_bass":    [(0.01, "very_low"), (0.03, "low"), (0.08, "medium"),
                    (0.15, "high"), (float("inf"), "very_high")],
    "bass":        [(0.08, "very_low"), (0.15, "low"), (0.30, "medium"),
                    (0.42, "high"), (float("inf"), "very_high")],
    "low_mid":     [(0.06, "very_low"), (0.10, "low"), (0.20, "medium"),
                    (0.28, "high"), (float("inf"), "very_high")],
    "mid":         [(0.10, "very_low"), (0.18, "low"), (0.34, "medium"),
                    (0.45, "high"), (float("inf"), "very_high")],
    "high_mid":    [(0.05, "very_low"), (0.10, "low"), (0.20, "medium"),
                    (0.28, "high"), (float("inf"), "very_high")],
    "high":        [(0.02, "very_low"), (0.05, "low"), (0.14, "medium"),
                    (0.22, "high"), (float("inf"), "very_high")],
    "ultra_high":  [(0.005, "very_low"), (0.01, "low"), (0.035, "medium"),
                    (0.07, "high"), (float("inf"), "very_high")],
}

# Klartextbeschreibungen pro Band + Kategorie → für mix_issues und KI-Kontext
_ISSUE_LABELS: dict[str, dict[str, str]] = {
    "sub_bass": {
        "very_low": "kaum Sub-Bass (20–60 Hz) — fehlendes Fundament",
        "very_high": "Sub-Bass-Rumble (20–60 Hz) — unkontrollierter Tiefton",
    },
    "bass": {
        "very_low": "zu wenig Bass (60–250 Hz) — dünner, körperloser Klang",
        "high":     "Bass-Überbetonung (60–250 Hz) — tendiert zu boomy",
        "very_high": "Boominess (60–250 Hz) — Bass dominiert zu stark",
    },
    "low_mid": {
        "very_low": "wenig Wärme (250–600 Hz) — klingt dünn oder kalt",
        "high":     "Matsch-Tendenz (250–600 Hz) — Mitten beginnen zu verschmieren",
        "very_high": "Muddiness (250–600 Hz) — Mix klingt matschig, Frequenzen verdecken sich",
    },
    "mid": {
        "very_low": "hohle Mitten (600–2500 Hz) — fehlende Präsenz und Vokalkörper",
        "very_high": "box-artige Mitten (600–2500 Hz) — unnatürliche Betonung",
    },
    "high_mid": {
        "very_low": "dumpfe Hochmitten (2500–6000 Hz) — fehlende Klarheit und Schneidigkeit",
        "high":     "Schärfe-Tendenz (2500–6000 Hz) — könnte bei längerem Hören ermüden",
        "very_high": "Harshness (2500–6000 Hz) — aggressiv, hört sich scharf/anstrengend an",
    },
    "high": {
        "very_low": "dunkler Mix (6–12 kHz) — fehlt Glanz und Luft",
        "very_high": "zu hell (6–12 kHz) — kann sibilant oder spitz klingen",
    },
    "ultra_high": {
        "very_low": "kein Air (12–20 kHz) — geschlossener, stumpfer Klang",
        "very_high": "übermäßige Luft (12–20 kHz) — ggf. Alias oder Rauschen",
    },
}


@dataclass
class DiagnosticResult:
    """
    Vollständiges Mix-Diagnose-Ergebnis.

    band_ratios:   Energie-Anteile pro Band (NormalizedFeature mit Diagnose-Kategorie)
    scores:        Abgeleitete Diagnose-Scores (boominess, muddiness, harshness, …)
    mix_balance:   0–1, Ähnlichkeit zum Referenz-Spektrum
    mix_issues:    Erkannte Probleme als KI-lesbare Strings
    """

    band_ratios: dict[str, NormalizedFeature] = field(default_factory=dict)
    scores:      dict[str, NormalizedFeature] = field(default_factory=dict)
    mix_balance: float = 0.0
    mix_issues:  list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "band_ratios":  {k: v.to_dict() for k, v in self.band_ratios.items()},
            "scores":       {k: v.to_dict() for k, v in self.scores.items()},
            "mix_balance":  round(self.mix_balance, 4),
            "mix_issues":   self.mix_issues,
        }

    def to_ki_context(self) -> str:
        lines: list[str] = ["=== Mix-Diagnose ==="]

        # Frequenz-Balance
        lines.append(f"Mix-Balance (Referenz-Nähe): {self.mix_balance:.2f}")

        # Band-Übersicht
        band_parts = []
        for band, f in self.band_ratios.items():
            band_parts.append(f"{band}={f.raw_value:.1%}({f.category})")
        lines.append("Frequenzbänder: " + "  ".join(band_parts))

        # Abgeleitete Scores
        for name, f in self.scores.items():
            if f.category and f.category != "medium":
                lines.append(f"{name}: {f.raw_value:.3f} ({f.category})")

        # Erkannte Probleme
        if self.mix_issues:
            lines.append("Erkannte Probleme:")
            for issue in self.mix_issues:
                lines.append(f"  ⚠ {issue}")
        else:
            lines.append("Keine kritischen Mix-Probleme erkannt.")

        return "\n".join(lines)


# ── Haupt-Extraktor ───────────────────────────────────────────────────────────

def extract_diagnostic_features(audio: np.ndarray, sr: int) -> DiagnosticResult:
    """
    Extrahiert Mix-Diagnose-Features aus einem Mono-Audio-Array.

    Args:
        audio: Mono float32 Array
        sr:    Sample-Rate in Hz

    Returns:
        DiagnosticResult mit band_ratios, scores, mix_balance, mix_issues
    """
    # STFT einmalig berechnen
    S = np.abs(librosa.stft(audio))
    n_fft = (S.shape[0] - 1) * 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    # ── 7-Band Energie-Anteile ────────────────────────────────────────────────
    total_power = float(np.sum(S ** 2))
    band_ratios: dict[str, NormalizedFeature] = {}

    actual: dict[str, float] = {}
    for band_name, (f_lo, f_hi) in DIAGNOSTIC_BANDS.items():
        mask = (freqs >= f_lo) & (freqs < f_hi)
        ratio = float(np.sum(S[mask] ** 2)) / (total_power + 1e-10)
        actual[band_name] = ratio

        # Kategorie via Band-spezifische Schwellwerte
        category = _categorize(ratio, _BAND_THRESHOLDS[band_name])
        band_ratios[band_name] = NormalizedFeature(
            name=band_name,
            raw_value=round(ratio, 4),
            unit="ratio",
            normalized=round(ratio, 4),
            category=category,
        )

    # ── Mix-Balance Score ─────────────────────────────────────────────────────
    # Totale Variation zwischen Ist- und Referenz-Spektrum, auf 0–1 normiert
    # 1.0 = identisch mit Referenz, 0.0 = maximal abweichend
    total_variation = sum(
        abs(actual.get(b, 0.0) - ref)
        for b, ref in REFERENCE_SPECTRUM.items()
    )
    mix_balance = round(max(0.0, 1.0 - total_variation), 4)

    # ── Abgeleitete Diagnose-Scores ───────────────────────────────────────────
    scores: dict[str, NormalizedFeature] = {}

    # Direkt die Band-Anteile verwenden — einfacher zu kalibrieren
    scores["boominess"]  = _score_feature("boominess",  actual["bass"],       0.15, 0.30)
    scores["muddiness"]  = _score_feature("muddiness",  actual["low_mid"],    0.10, 0.20)
    scores["harshness"]  = _score_feature("harshness",  actual["high_mid"],   0.10, 0.20)
    scores["brightness"] = _score_feature("brightness", actual["high"],       0.05, 0.14)
    scores["air"]        = _score_feature("air",        actual["ultra_high"], 0.01, 0.035)

    # ── Mix-Issues ────────────────────────────────────────────────────────────
    mix_issues = _collect_issues(band_ratios)

    return DiagnosticResult(
        band_ratios=band_ratios,
        scores=scores,
        mix_balance=mix_balance,
        mix_issues=mix_issues,
    )


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _categorize(value: float, thresholds: list[tuple[float, str]]) -> str:
    for upper, cat in thresholds:
        if value <= upper:
            return cat
    return thresholds[-1][1]


def _score_feature(
    name: str, value: float, medium_lo: float, medium_hi: float
) -> NormalizedFeature:
    """
    Mappt einen abgeleiteten Score auf NormalizedFeature.
    medium_lo/hi definieren den "gesunden" Bereich.
    """
    if value < medium_lo * 0.5:
        category = "very_low"
    elif value < medium_lo:
        category = "low"
    elif value <= medium_hi:
        category = "medium"
    elif value <= medium_hi * 1.5:
        category = "high"
    else:
        category = "very_high"

    # Normalisiert relativ zu medium_hi (1.0 = obere Grenze des gesunden Bereichs)
    normalized = round(min(value / (medium_hi + 1e-10), 2.0), 4)

    return NormalizedFeature(
        name=name,
        raw_value=round(value, 4),
        unit="ratio",
        normalized=normalized,
        category=category,
    )


def _collect_issues(band_ratios: dict[str, NormalizedFeature]) -> list[str]:
    """Sammelt alle Kategorie-basierten Problembeschreibungen."""
    issues: list[str] = []
    for band_name, feature in band_ratios.items():
        cat = feature.category
        if cat and cat != "medium" and cat != "low":
            label = _ISSUE_LABELS.get(band_name, {}).get(cat)
            if label:
                issues.append(label)
    return issues
