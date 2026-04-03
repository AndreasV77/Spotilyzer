"""
FeatureExtractor — zentrale Orchestrierung der Phase-1/2-Analyse.

Lädt Audio via librosa, delegiert an spectral / temporal / production /
diagnostic Extraktoren und liefert ein SpectralAnalysisResult zurück.

Verwendung:
    from spotilyzer.analysis import FeatureExtractor

    extractor = FeatureExtractor()
    result = extractor.extract("track.mp3")

    print(result.to_ki_context())        # Natürlichsprachliche Zusammenfassung
    result_dict = result.to_dict()       # Für JSON-Export / Logging
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from .normalization import NormalizedFeature
from .spectral_features import extract_spectral_features
from .temporal_features import extract_temporal_features
from .production_features import extract_production_features
from .diagnostic_features import DiagnosticResult, extract_diagnostic_features
from .role_features import RoleResult, extract_role_features


@dataclass
class SpectralAnalysisResult:
    """
    Vollständiges Analyse-Ergebnis (Tier 2A: Interpretable Measurements).

    Attribute:
        spectral:   Spektrale Features (Centroid, Bandwidth, Rolloff, …)
        temporal:   Zeitbasierte Features (BPM, Stability, Onset Rate, …)
        production: Produktions-Features (LUFS, Dynamic Range, Stereo Width, …)
        source_path: Pfad zur analysierten Datei (optional)
        sample_rate: Sample-Rate nach Resampling
    """

    spectral:    dict[str, NormalizedFeature] = field(default_factory=dict)
    temporal:    dict[str, NormalizedFeature] = field(default_factory=dict)
    production:  dict[str, NormalizedFeature] = field(default_factory=dict)
    diagnostic:  Optional[DiagnosticResult]   = None
    roles:       Optional[RoleResult]         = None
    source_path: str = ""
    sample_rate: int = 0

    # ── Serialisierung ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialisiert alle Features für JSON-Export / API."""
        d = {
            "source": self.source_path,
            "sample_rate": self.sample_rate,
            "spectral":    {k: v.to_dict() for k, v in self.spectral.items()},
            "temporal":    {k: v.to_dict() for k, v in self.temporal.items()},
            "production":  {k: v.to_dict() for k, v in self.production.items()},
        }
        if self.diagnostic is not None:
            d["diagnostic"] = self.diagnostic.to_dict()
        if self.roles is not None:
            d["roles"] = self.roles.to_dict()
        return d

    # ── KI-lesbarer Kontext ───────────────────────────────────────────────────

    def to_ki_context(self) -> str:
        """
        Generiert einen natürlichsprachlichen Kontext für LLM-Prompts.

        Nur Felder mit vorhandenem Wert werden ausgegeben.
        Kategorien (very_low … very_high) erlauben direkte semantische Aussagen.
        """
        lines: list[str] = []

        def _fmt(f: NormalizedFeature | None, fmt: str) -> str:
            if f is None:
                return "—"
            cat = f" ({f.category})" if f.category else ""
            return fmt.format(v=f.raw_value) + cat

        def _get(d: dict, key: str) -> NormalizedFeature | None:
            return d.get(key)

        # ── Spektrum ──────────────────────────────────────────────────────────
        sp = self.spectral
        if sp:
            lines.append("=== Spektrum ===")
            if c := _get(sp, "spectral_centroid"):
                lines.append(f"Spektraler Schwerpunkt : {_fmt(c, '{v:.0f} Hz')}")
            if bw := _get(sp, "spectral_bandwidth"):
                lines.append(f"Spektrale Breite       : {_fmt(bw, '{v:.0f} Hz')}")
            if ro := _get(sp, "spectral_rolloff"):
                lines.append(f"Rolloff (85%)          : {_fmt(ro, '{v:.0f} Hz')}")
            if fl := _get(sp, "spectral_flatness"):
                lines.append(f"Tonalität/Rauschanteil : {_fmt(fl, '{v:.4f}')}")
            if ct := _get(sp, "spectral_contrast"):
                lines.append(f"Spektr. Kontrast (∅)   : {ct.raw_value:.1f} dB")
            if tl := _get(sp, "spectral_tilt"):
                lines.append(f"Spektrale Neigung      : {tl.raw_value:+.2f} dB/oct")
            band_parts = []
            for band in ("sub", "bass", "mid", "high"):
                if e := _get(sp, f"energy_{band}"):
                    band_parts.append(f"{band}={e.raw_value:.1%}")
            if band_parts:
                lines.append(f"4-Band-Energie         : {', '.join(band_parts)}")

        # ── Rhythmus / Zeit ───────────────────────────────────────────────────
        tm = self.temporal
        if tm:
            lines.append("=== Rhythmus ===")
            if bpm := _get(tm, "bpm"):
                lines.append(f"Tempo                  : {bpm.raw_value} BPM")
            if st := _get(tm, "tempo_stability"):
                lines.append(f"Tempo-Stabilität       : {_fmt(st, '{v:.2f}')}")
            if or_ := _get(tm, "onset_rate"):
                lines.append(f"Onset-Rate             : {_fmt(or_, '{v:.2f} /s')}")
            if bs := _get(tm, "beat_strength"):
                lines.append(f"Beat-Stärke            : {_fmt(bs, '{v:.2f}')}")
            if hp := _get(tm, "hpss_ratio"):
                lines.append(f"Harmonisch/Perkussiv   : {_fmt(hp, '{v:.2f}')}")

        # ── Produktion ────────────────────────────────────────────────────────
        pr = self.production
        if pr:
            lines.append("=== Produktion ===")
            if lu := _get(pr, "lufs"):
                lines.append(f"LUFS (Integrated)      : {lu.raw_value:.1f} dBFS")
            if dr := _get(pr, "dynamic_range_db"):
                lines.append(f"Dynamikumfang          : {_fmt(dr, '{v:.1f} dB')}")
            if cf := _get(pr, "crest_factor"):
                lines.append(f"Crest Factor           : {_fmt(cf, '{v:.2f}')}")
            if sw := _get(pr, "stereo_width"):
                lines.append(f"Stereobreite           : {_fmt(sw, '{v:.2f}')}")
            if ms := _get(pr, "mid_side_ratio"):
                lines.append(f"Mid/Side-Verhältnis    : {ms.raw_value:.2f}")
            if cl := _get(pr, "clipping_ratio"):
                if cl.raw_value > 0.001:
                    lines.append(f"Clipping               : {cl.raw_value:.2%} ⚠")

        # ── Mix-Diagnose ──────────────────────────────────────────────────────
        if self.diagnostic is not None:
            lines.append(self.diagnostic.to_ki_context())

        # ── Instrument-Rollen ─────────────────────────────────────────────────
        if self.roles is not None:
            lines.append(self.roles.to_ki_context())

        return "\n".join(lines)


# ── FeatureExtractor ──────────────────────────────────────────────────────────

class FeatureExtractor:
    """
    Zentrale Klasse für Phase-1-Feature-Extraktion.

    Lädt Audio, resampled auf TARGET_SR, delegiert an die Einzel-Extraktoren.
    Kein State / keine Modelle — kann direkt instanziiert werden.
    """

    TARGET_SR = 22050  # librosa-Standard, balanciert Qualität und Geschwindigkeit

    def extract(self, audio_path: str | Path) -> SpectralAnalysisResult:
        """
        Extrahiert alle Phase-1-Features aus einer Audio-Datei.

        Args:
            audio_path: Pfad zur Audio-Datei (alle librosa-unterstützten Formate)

        Returns:
            SpectralAnalysisResult

        Raises:
            FileNotFoundError: wenn Datei nicht existiert
            RuntimeError:      bei nicht unterstütztem Audio-Format
        """
        import librosa

        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio-Datei nicht gefunden: {path}")

        # Stereo laden (mono=False), dann ggf. auf Mono falten
        audio_stereo, _ = librosa.load(
            str(path), sr=self.TARGET_SR, mono=False
        )

        # Sicherstellen: shape immer (channels, samples)
        if audio_stereo.ndim == 1:
            audio_stereo = audio_stereo[np.newaxis, :]

        audio_mono = audio_stereo.mean(axis=0)

        spectral   = extract_spectral_features(audio_mono, self.TARGET_SR)
        temporal   = extract_temporal_features(audio_mono, self.TARGET_SR)
        production = extract_production_features(audio_stereo, self.TARGET_SR)
        diagnostic = extract_diagnostic_features(audio_mono, self.TARGET_SR)
        roles      = extract_role_features(audio_mono, self.TARGET_SR)

        return SpectralAnalysisResult(
            spectral=spectral,
            temporal=temporal,
            production=production,
            diagnostic=diagnostic,
            roles=roles,
            source_path=str(path),
            sample_rate=self.TARGET_SR,
        )
