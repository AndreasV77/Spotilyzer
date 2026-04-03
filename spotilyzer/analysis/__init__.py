"""
spotilyzer.analysis — Phase-1 Spektral-Feature-Extraktion.

Öffentliche API:
    FeatureExtractor       — lädt Audio, orchestriert alle Extraktoren
    SpectralAnalysisResult — strukturiertes Ergebnis (Tier 2A)
    NormalizedFeature      — Feature mit Rohwert, normalisiertem Wert und Kategorie
"""

from .feature_extractor import FeatureExtractor, SpectralAnalysisResult
from .normalization import NormalizedFeature, normalize_feature
from .diagnostic_features import DiagnosticResult, extract_diagnostic_features
from .role_features import RoleResult, extract_role_features

__all__ = [
    "FeatureExtractor",
    "SpectralAnalysisResult",
    "DiagnosticResult",
    "RoleResult",
    "NormalizedFeature",
    "normalize_feature",
    "extract_diagnostic_features",
    "extract_role_features",
]
