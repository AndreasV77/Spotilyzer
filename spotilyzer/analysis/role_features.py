"""
Role Features (Phase 2, Tier 2C).

Schätzt die relative Prominenz einzelner Instrument-Rollen via HPSS
(Harmonic-Percussive Source Separation).

Das Audio wird in zwei Signale getrennt:
  - Perkussiv (P): Transienten, Drums, Perkussion
  - Harmonisch (H): Sustained tones, Melodie, Harmonie, Stimme

Aus jedem Anteil werden Frequenzband-Energien berechnet und normiert.

Perkussive Rollen (Anteil an Gesamt-Perkussivenergie):
    kick_prominence   — 40–120 Hz    Kick-Drum, Sub-Punch
    snare_prominence  — 150–400 Hz   Snare-Body, Tom-Snap
    hihat_prominence  — 6–15 kHz     Hi-Hat, Cymbal-Shimmer
    perc_density      — Onsets/s im perkussiven Signal

Harmonische Rollen (Anteil an Gesamt-Harmonikenergie):
    bass_line         — 60–300 Hz    Bass-Guitar, Sub-Bass-Melodie
    vocal_zone        — 250–3000 Hz  Stimme, Piano, Akustik-Gitarre
    lead_presence     — 2–8 kHz      Lead-Gitarre, Solo, obere Harmonie
    harmonic_richness — 0–1          Anzahl signifikanter Partialtöne (Vollheit)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import librosa

from .normalization import NormalizedFeature


# ── Frequenzbänder für Rollen ─────────────────────────────────────────────────

PERC_BANDS: dict[str, tuple[int, int]] = {
    "kick":   (40,   120),   # Kick-Drum-Fundamentale und Sub-Punch
    "snare":  (150,  400),   # Snare-Body, Tom-Attack
    "hihat":  (6000, 15000), # Cymbal-Shimmer, Hi-Hat
}

HARM_BANDS: dict[str, tuple[int, int]] = {
    "bass_line":    (60,   300),  # Bass-Guitar-Fundamentale
    "vocal_zone":   (250, 3000),  # Stimme, Piano, Gitarren-Körper
    "lead_presence":(2000, 8000), # Lead-Gitarre, Solo, obere Harmonie
}

# Kategorie-Schwellwerte (Anteil am jeweiligen H- oder P-Signal)
_THRESHOLDS: dict[str, list[tuple[float, str]]] = {
    "kick_prominence":  [(0.10, "very_low"), (0.18, "low"), (0.32, "medium"),
                         (0.48, "high"), (float("inf"), "very_high")],
    "snare_prominence": [(0.05, "very_low"), (0.12, "low"), (0.22, "medium"),
                         (0.35, "high"), (float("inf"), "very_high")],
    "hihat_prominence": [(0.03, "very_low"), (0.08, "low"), (0.18, "medium"),
                         (0.30, "high"), (float("inf"), "very_high")],
    "perc_density":     [(1.0,  "very_low"), (3.0,  "low"), (7.0,  "medium"),
                         (12.0, "high"), (float("inf"), "very_high")],
    "bass_line":        [(0.05, "very_low"), (0.10, "low"), (0.22, "medium"),
                         (0.38, "high"), (float("inf"), "very_high")],
    "vocal_zone":       [(0.20, "very_low"), (0.35, "low"), (0.55, "medium"),
                         (0.70, "high"), (float("inf"), "very_high")],
    "lead_presence":    [(0.05, "very_low"), (0.12, "low"), (0.22, "medium"),
                         (0.35, "high"), (float("inf"), "very_high")],
    "harmonic_richness":[(0.50, "very_low"), (0.65, "low"), (0.78, "medium"),
                         (0.88, "high"), (float("inf"), "very_high")],
}

# Normalisierungs-Ranges (0–1) pro Feature
_NORM_RANGES: dict[str, tuple[float, float]] = {
    "kick_prominence":   (0.0, 0.6),
    "snare_prominence":  (0.0, 0.5),
    "hihat_prominence":  (0.0, 0.4),
    "perc_density":      (0.0, 20.0),
    "bass_line":         (0.0, 0.6),
    "vocal_zone":        (0.0, 1.0),
    "lead_presence":     (0.0, 0.5),
    "harmonic_richness": (0.0, 1.0),
}


@dataclass
class RoleResult:
    """
    Instrument-Rollen Analyse.

    percussive: Kick, Snare, HiHat, Perkussions-Dichte
    harmonic:   Bass-Line, Vokal-Zone, Lead-Präsenz, Harmonische Fülle
    dominant_roles: Top-3 prominenteste Rollen als Strings (KI-lesbar)
    hp_ratio:   Harmonisch/Perkussiv-Energieverhältnis (Referenz)
    """

    percussive:     dict[str, NormalizedFeature] = field(default_factory=dict)
    harmonic:       dict[str, NormalizedFeature] = field(default_factory=dict)
    dominant_roles: list[str] = field(default_factory=list)
    hp_ratio:       float = 1.0

    def to_dict(self) -> dict:
        return {
            "percussive":     {k: v.to_dict() for k, v in self.percussive.items()},
            "harmonic":       {k: v.to_dict() for k, v in self.harmonic.items()},
            "dominant_roles": self.dominant_roles,
            "hp_ratio":       round(self.hp_ratio, 3),
        }

    def to_ki_context(self) -> str:
        lines = ["=== Instrument-Rollen ==="]

        lines.append(f"Harmonisch/Perkussiv-Verhältnis: {self.hp_ratio:.2f}"
                     f"  ({'harmonisch dominiert' if self.hp_ratio > 1.5 else 'perkussiv dominiert' if self.hp_ratio < 0.7 else 'ausgewogen'})")

        # Perkussive Rollen
        p = self.percussive
        perc_parts = []
        for key, label in [("kick_prominence", "Kick"), ("snare_prominence", "Snare"),
                            ("hihat_prominence", "Hi-Hat")]:
            if f := p.get(key):
                perc_parts.append(f"{label}={f.raw_value:.2f}({f.category})")
        if pd := p.get("perc_density"):
            perc_parts.append(f"Dichte={pd.raw_value:.1f}/s({pd.category})")
        if perc_parts:
            lines.append("Perkussiv  : " + "  ".join(perc_parts))

        # Harmonische Rollen
        h = self.harmonic
        harm_parts = []
        for key, label in [("bass_line", "Bass"), ("vocal_zone", "Vokal/Mid"),
                            ("lead_presence", "Lead"), ("harmonic_richness", "Fülle")]:
            if f := h.get(key):
                harm_parts.append(f"{label}={f.raw_value:.2f}({f.category})")
        if harm_parts:
            lines.append("Harmonisch : " + "  ".join(harm_parts))

        if self.dominant_roles:
            lines.append("Dominante Rollen: " + ", ".join(self.dominant_roles))

        return "\n".join(lines)


# ── Haupt-Extraktor ───────────────────────────────────────────────────────────

def extract_role_features(audio: np.ndarray, sr: int) -> RoleResult:
    """
    Extrahiert Instrument-Rollen-Features aus einem Mono-Audio-Array.

    Args:
        audio: Mono float32 Array (empfohlen: voller Track, mind. 10 s)
        sr:    Sample-Rate in Hz

    Returns:
        RoleResult mit percussive, harmonic, dominant_roles, hp_ratio
    """
    # ── HPSS ─────────────────────────────────────────────────────────────────
    # margin=1 (Default) = sanfte Trennung — robuster bei Heavy Metal/Distortion
    # (margin=3 würde Distortion-Gitarren fälschlicherweise als perkussiv klassifizieren)
    harmonic, percussive = librosa.effects.hpss(audio, margin=1)

    h_energy = float(np.sum(harmonic ** 2))
    p_energy = float(np.sum(percussive ** 2))
    hp_ratio = h_energy / (p_energy + 1e-10)

    # ── STFTs einmalig ────────────────────────────────────────────────────────
    S_harm = np.abs(librosa.stft(harmonic))
    S_perc = np.abs(librosa.stft(percussive))
    n_fft = (S_harm.shape[0] - 1) * 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    # ── Perkussive Rollen ─────────────────────────────────────────────────────
    perc_total = float(np.sum(S_perc ** 2)) + 1e-10
    perc_features: dict[str, NormalizedFeature] = {}

    for band_key, (f_lo, f_hi) in PERC_BANDS.items():
        mask = (freqs >= f_lo) & (freqs < f_hi)
        ratio = float(np.sum(S_perc[mask] ** 2)) / perc_total
        feat_key = f"{band_key}_prominence" if band_key != "hihat" else "hihat_prominence"
        perc_features[feat_key] = _make_feature(feat_key, ratio, "ratio")

    # Perkussions-Dichte (Onsets/s im perkussiven Signal)
    onset_env_p = librosa.onset.onset_strength(y=percussive, sr=sr)
    onsets_p = librosa.onset.onset_detect(onset_envelope=onset_env_p, sr=sr, units="time")
    duration = len(audio) / sr
    perc_density = len(onsets_p) / duration if duration > 0 else 0.0
    perc_features["perc_density"] = _make_feature("perc_density", round(perc_density, 2), "/s")

    # ── Harmonische Rollen ────────────────────────────────────────────────────
    harm_total = float(np.sum(S_harm ** 2)) + 1e-10
    harm_features: dict[str, NormalizedFeature] = {}

    for band_key, (f_lo, f_hi) in HARM_BANDS.items():
        mask = (freqs >= f_lo) & (freqs < f_hi)
        ratio = float(np.sum(S_harm[mask] ** 2)) / harm_total
        harm_features[band_key] = _make_feature(band_key, ratio, "ratio")

    # Harmonische Fülle via spektrale Entropie (robuster als Bin-Count)
    # Hohe Entropie = Energie gleichmäßig verteilt = reicher, voller Klang
    # Niedrige Entropie = Energie konzentriert auf wenige Bins = sparse/tonal
    mean_spectrum = np.mean(S_harm ** 2, axis=1) + 1e-10
    p = mean_spectrum / mean_spectrum.sum()
    max_entropy = np.log(len(p))  # Entropy eines uniform-Spektrums
    entropy = -float(np.sum(p * np.log(p)))
    richness = entropy / max_entropy if max_entropy > 0 else 0.0
    harm_features["harmonic_richness"] = _make_feature("harmonic_richness", round(richness, 4), "")

    # ── Dominante Rollen ──────────────────────────────────────────────────────
    dominant = _find_dominant_roles(perc_features, harm_features)

    return RoleResult(
        percussive=perc_features,
        harmonic=harm_features,
        dominant_roles=dominant,
        hp_ratio=round(hp_ratio, 3),
    )


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _make_feature(name: str, value: float, unit: str) -> NormalizedFeature:
    """Erstellt NormalizedFeature mit Threshold-Kategorie und linearer Normalisierung."""
    # Kategorie
    category = None
    if name in _THRESHOLDS:
        for upper, cat in _THRESHOLDS[name]:
            if value <= upper:
                category = cat
                break

    # Normalisierung 0–1
    normalized = None
    if name in _NORM_RANGES:
        lo, hi = _NORM_RANGES[name]
        if hi > lo:
            normalized = round(max(0.0, min(1.0, (value - lo) / (hi - lo))), 4)

    return NormalizedFeature(
        name=name, raw_value=value, unit=unit,
        normalized=normalized, category=category,
    )


def _find_dominant_roles(
    perc: dict[str, NormalizedFeature],
    harm: dict[str, NormalizedFeature],
) -> list[str]:
    """
    Bestimmt die 3 prominentesten Rollen über alle Features.
    Gibt KI-lesbare Labels zurück, z.B. ["Bass-Line (high)", "Kick (medium)"].
    """
    labels = {
        "kick_prominence":   "Kick-Drum",
        "snare_prominence":  "Snare/Perkussion",
        "hihat_prominence":  "Hi-Hat/Cymbal",
        "bass_line":         "Bass-Line",
        "vocal_zone":        "Vokal/Mittenbereich",
        "lead_presence":     "Lead/Solo",
        "harmonic_richness": "Harmonische Fülle",
    }
    category_rank = {"very_high": 5, "high": 4, "medium": 3, "low": 2, "very_low": 1}

    all_features = {**perc, **harm}
    scored = []
    for key, label in labels.items():
        if f := all_features.get(key):
            rank = category_rank.get(f.category or "low", 0)
            if rank >= 4:  # nur "high" und "very_high"
                scored.append((rank, f.raw_value, f"{label} ({f.category})", key))

    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [s[2] for s in scored[:3]]
