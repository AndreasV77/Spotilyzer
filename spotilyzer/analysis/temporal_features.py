"""
Zeitbasierte Features (Tier 2A).

Features:
    bpm                  — Tempo in BPM (librosa Dynamic-Programming Beat Tracker)
    tempo_stability      — Tempo-Konsistenz 0=variabel, 1=metronom-stabil
    onset_rate           — Transientenanzahl pro Sekunde
    onset_strength_mean  — Mittlere Onset-Stärke (relativer Wert)
    beat_strength        — Konfidenz der Beat-Detektion 0–1
    hpss_ratio           — Harmonisch/Perkussiv-Energie-Verhältnis
"""

from __future__ import annotations

import numpy as np
import librosa

from .normalization import NormalizedFeature, normalize_feature

# Hop-Length für Onset-Analyse (librosa-Standard)
_HOP_LENGTH = 512


def extract_temporal_features(
    audio: np.ndarray, sr: int
) -> dict[str, NormalizedFeature]:
    """
    Extrahiert zeitbasierte Features aus einem Mono-Audio-Array.

    Args:
        audio: Mono float32 Array
        sr:    Sample-Rate in Hz

    Returns:
        Dict von Feature-Name → NormalizedFeature
    """
    results: dict[str, NormalizedFeature] = {}

    # Onset-Envelope einmal berechnen — für alle Tempo-/Beat-Features wiederverwendet
    onset_env = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=_HOP_LENGTH)

    # ── BPM + Tempo-Stabilität ────────────────────────────────────────────────
    bpm, tempo_stability = _estimate_bpm_and_stability(onset_env, sr)
    if bpm is not None:
        results["bpm"] = NormalizedFeature(
            name="bpm", raw_value=round(bpm, 1), unit="BPM",
            normalized=None, category=None,
        )
    results["tempo_stability"] = normalize_feature(
        "tempo_stability", tempo_stability, ""
    )

    # ── Onset Rate (/s) ───────────────────────────────────────────────────────
    duration_sec = len(audio) / sr
    onsets = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, hop_length=_HOP_LENGTH, units="time"
    )
    onset_rate = len(onsets) / duration_sec if duration_sec > 0 else 0.0
    results["onset_rate"] = normalize_feature("onset_rate", round(onset_rate, 2), "/s")

    # ── Onset Strength Mean ───────────────────────────────────────────────────
    onset_strength_mean = float(np.mean(onset_env))
    results["onset_strength_mean"] = NormalizedFeature(
        name="onset_strength_mean",
        raw_value=round(onset_strength_mean, 4),
        unit="",
        normalized=None,
        category=None,
    )

    # ── Beat Strength ─────────────────────────────────────────────────────────
    # Onset-Stärke bei erkannten Beat-Positionen relativ zum Maximum
    _, beats = librosa.beat.beat_track(
        onset_envelope=onset_env, sr=sr, hop_length=_HOP_LENGTH
    )
    if len(beats) > 0 and np.max(onset_env) > 1e-10:
        # Clips auf gültige Indizes
        beats_clipped = beats[beats < len(onset_env)]
        beat_strength = float(np.mean(onset_env[beats_clipped])) / float(np.max(onset_env))
        results["beat_strength"] = normalize_feature(
            "beat_strength", round(beat_strength, 4), ""
        )

    # ── HPSS Ratio (Harmonisch / Perkussiv) ──────────────────────────────────
    harmonic, percussive = librosa.effects.hpss(audio)
    h_energy = float(np.sum(harmonic ** 2))
    p_energy = float(np.sum(percussive ** 2))
    hpss_ratio = h_energy / (p_energy + 1e-10)
    results["hpss_ratio"] = normalize_feature("hpss_ratio", round(hpss_ratio, 4), "H/P")

    return results


def _estimate_bpm_and_stability(
    onset_env: np.ndarray, sr: int
) -> tuple[float | None, float]:
    """
    Schätzt globales BPM und Tempo-Stabilität aus der Onset-Envelope.

    Tempo-Stabilität:
        Variationskoeffizient lokaler Tempo-Schätzungen (4-Sekunden-Fenster).
        stability = 1 − CV, clipped to [0, 1].
        1.0 = metronom-stabil, 0.0 = keine erkennbare Periodizität.

    Returns:
        (bpm, stability)
    """
    # ── Globales Tempo ────────────────────────────────────────────────────────
    tempo_dp, _ = librosa.beat.beat_track(
        onset_envelope=onset_env, sr=sr, hop_length=_HOP_LENGTH
    )
    tempo_dp = float(np.atleast_1d(tempo_dp)[0])

    tempo_global = librosa.feature.tempo(
        onset_envelope=onset_env, sr=sr, hop_length=_HOP_LENGTH
    )
    tempo_global = float(np.atleast_1d(tempo_global)[0])

    # Oktavkorrektur: bevorzuge 70–180 BPM
    def _correct(t: float) -> float:
        if t > 180 and 70 <= t / 2 <= 180:
            return t / 2
        if t < 70 and 70 <= t * 2 <= 180:
            return t * 2
        return t

    tempo_dp = _correct(tempo_dp)
    tempo_global = _correct(tempo_global)
    bpm = (tempo_dp + tempo_global) / 2 if abs(tempo_dp - tempo_global) < 5 else tempo_dp

    if not (40 <= bpm <= 240):
        bpm = None

    # ── Tempo-Stabilität ──────────────────────────────────────────────────────
    # 4-Sekunden-Fenster, 50% Überlappung
    frames_per_4s = int(sr / _HOP_LENGTH * 4)
    step = frames_per_4s // 2

    local_tempos: list[float] = []
    for i in range(0, len(onset_env) - frames_per_4s, step):
        chunk = onset_env[i : i + frames_per_4s]
        t = librosa.feature.tempo(
            onset_envelope=chunk, sr=sr, hop_length=_HOP_LENGTH
        )
        local_tempos.append(float(np.atleast_1d(t)[0]))

    if len(local_tempos) < 2:
        return bpm, 0.8  # Zu kurzer Track für sinnvolle Stabilitätsmessung

    arr = np.array(local_tempos)
    cv = float(np.std(arr)) / (float(np.mean(arr)) + 1e-10)
    stability = round(max(0.0, min(1.0, 1.0 - cv)), 4)

    return bpm, stability
