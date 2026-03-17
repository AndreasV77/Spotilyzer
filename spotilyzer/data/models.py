"""
Datenmodelle für Spotilyzer.
Zentrale Dataclasses für Analyse-Ergebnisse, Audio-Metadaten und App-State.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class Rating(str, Enum):
    """Track-Bewertung."""
    HIT = "hit"
    MID = "mid"
    FLOP = "flop"

    @property
    def emoji(self) -> str:
        return {"hit": "\U0001f525", "mid": "\u2796", "flop": "\U0001f480"}[self.value]

    @property
    def label(self) -> str:
        return self.value.upper()


class AppMode(str, Enum):
    """Drei-Stufen UX-Modus."""
    SIMPLE = "simple"
    BALANCED = "balanced"
    PRO = "pro"

    @property
    def display_name(self) -> str:
        return {"simple": "Simpel", "balanced": "Ausgewogen", "pro": "Profi"}[self.value]


class SortMode(str, Enum):
    """Sortier-Modus für Ergebnisse."""
    SCORE = "score"
    TIME = "time"
    NAME = "name"


# ══════════════════════════════════════════════════════════════════════════════
# DATENMODELLE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AudioInfo:
    """Technische Metadaten eines Audio-Tracks (13 Felder)."""

    # Basis-Info (immer verfügbar via torchaudio.info())
    duration_sec: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    bitrate: Optional[int] = None       # kbps, None wenn nicht ermittelbar
    format: str = ""                     # "mp3", "flac", "wav", ...
    file_size_bytes: int = 0

    # Berechnete Metriken
    bpm: Optional[float] = None          # Geschätztes Tempo (torchaudio onset detection)
    lufs: Optional[float] = None         # Integrated Loudness (EBU R128)
    key: Optional[str] = None            # Geschätzte Tonart (z.B. "C major", "A minor")
    energy: Optional[float] = None       # Spektrale Energie (RMS-basiert, 0.0-1.0)

    @property
    def duration_formatted(self) -> str:
        """Dauer als MM:SS formatiert."""
        minutes = int(self.duration_sec // 60)
        seconds = int(self.duration_sec % 60)
        return f"{minutes}:{seconds:02d}"

    @property
    def file_size_formatted(self) -> str:
        """Dateigröße menschenlesbar (KB/MB)."""
        if self.file_size_bytes < 1024:
            return f"{self.file_size_bytes} B"
        elif self.file_size_bytes < 1024 * 1024:
            return f"{self.file_size_bytes / 1024:.1f} KB"
        else:
            return f"{self.file_size_bytes / (1024 * 1024):.1f} MB"

    @property
    def channels_label(self) -> str:
        """Kanal-Beschreibung."""
        return {1: "Mono", 2: "Stereo"}.get(self.channels, f"{self.channels}ch")

    def to_dict(self) -> dict:
        """Serialisiert für JSON-Export (ohne None-Werte)."""
        d = {
            "duration_sec": round(self.duration_sec, 2),
            "duration_formatted": self.duration_formatted,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "channels_label": self.channels_label,
            "format": self.format,
            "file_size_bytes": self.file_size_bytes,
            "file_size_formatted": self.file_size_formatted,
        }
        if self.bitrate is not None:
            d["bitrate_kbps"] = self.bitrate
        if self.bpm is not None:
            d["bpm"] = round(self.bpm, 1)
        if self.lufs is not None:
            d["lufs"] = round(self.lufs, 1)
        if self.key is not None:
            d["key"] = self.key
        if self.energy is not None:
            d["energy"] = round(self.energy, 4)
        return d


@dataclass
class ModelInfo:
    """Metadaten zum verwendeten Analyse-Modell (für Vergleichbarkeit)."""

    model_name: str = ""                 # Dateiname des Modells (z.B. "spotilyzer_model.joblib")
    model_path: str = ""                 # Vollständiger Pfad
    embedder: str = "MERT-v1-95M"        # Name des Embedding-Modells
    device: str = ""                     # "cuda" oder "cpu"
    training_date: Optional[str] = None  # Trainings-Datum (aus training_report.json)
    dataset_info: Optional[str] = None   # Beschreibung des Trainings-Datensatzes

    def to_dict(self) -> dict:
        d: dict = {
            "model_name": self.model_name,
            "embedder": self.embedder,
            "device": self.device,
        }
        if self.model_path:
            d["model_path"] = self.model_path
        if self.training_date:
            d["training_date"] = self.training_date
        if self.dataset_info:
            d["dataset_info"] = self.dataset_info
        return d


@dataclass
class AnalysisResult:
    """Vollständiges Analyse-Ergebnis eines Tracks."""

    file: str                            # Dateiname (nur Name, kein Pfad)
    path: str                            # Vollständiger Pfad als String
    timestamp: str                       # ISO 8601 Zeitstempel
    rating: str = ""                     # "hit", "mid", "flop"
    confidence: float = 0.0              # 0.0 - 1.0 (max der Probabilities)
    probabilities: dict = field(default_factory=dict)  # {"hit": 0.85, "mid": 0.10, "flop": 0.05}
    audio_info: Optional[AudioInfo] = None
    model_info: Optional[ModelInfo] = None  # Modell-/Datensatz-Info für Vergleichbarkeit
    clap_result: Optional["CLAPResult"] = None  # Zero-Shot Genre/Mood (optional, nur wenn aktiviert)
    error: Optional[str] = None          # Fehlermeldung wenn Analyse fehlschlug

    # Nicht persistiert (nur für aktive GUI-Session)
    _waveform: Optional[np.ndarray] = field(default=None, repr=False, compare=False)

    @property
    def is_error(self) -> bool:
        return self.error is not None

    @property
    def rating_enum(self) -> Optional[Rating]:
        if self.rating in ("hit", "mid", "flop"):
            return Rating(self.rating)
        return None

    @property
    def hit_probability(self) -> float:
        return self.probabilities.get("hit", 0.0)

    def to_dict(self) -> dict:
        """Serialisiert für JSON-Export (kompatibel mit bestehendem Format)."""
        d = {
            "file": self.file,
            "path": self.path,
            "timestamp": self.timestamp,
        }
        if self.error:
            d["error"] = self.error
        else:
            d["rating"] = self.rating
            d["confidence"] = round(self.confidence, 6)
            d["probabilities"] = {
                k: round(v, 6) for k, v in self.probabilities.items()
            }
            if self.audio_info:
                d["audio_info"] = self.audio_info.to_dict()
            if self.model_info:
                d["model_info"] = self.model_info.to_dict()
            if self.clap_result:
                d["clap_result"] = self.clap_result.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "AnalysisResult":
        """Deserialisiert aus JSON (kompatibel mit v1.0 und v2.0 Format)."""
        audio_info = None
        if "audio_info" in data and data["audio_info"]:
            ai = data["audio_info"]
            audio_info = AudioInfo(
                duration_sec=ai.get("duration_sec", 0.0),
                sample_rate=ai.get("sample_rate", 0),
                channels=ai.get("channels", 0),
                bitrate=ai.get("bitrate_kbps"),
                format=ai.get("format", ""),
                file_size_bytes=ai.get("file_size_bytes", 0),
                bpm=ai.get("bpm"),
                lufs=ai.get("lufs"),
                key=ai.get("key"),
                energy=ai.get("energy"),
            )

        # Model-Info deserialisieren (v2.1+)
        model_info = None
        if "model_info" in data and data["model_info"]:
            mi = data["model_info"]
            model_info = ModelInfo(
                model_name=mi.get("model_name", ""),
                model_path=mi.get("model_path", ""),
                embedder=mi.get("embedder", "MERT-v1-95M"),
                device=mi.get("device", ""),
                training_date=mi.get("training_date"),
                dataset_info=mi.get("dataset_info"),
            )

        clap_result = None
        if "clap_result" in data and data["clap_result"]:
            clap_result = CLAPResult.from_dict(data["clap_result"])

        return cls(
            file=data.get("file", ""),
            path=data.get("path", ""),
            timestamp=data.get("timestamp", ""),
            rating=data.get("rating", ""),
            confidence=data.get("confidence", 0.0),
            probabilities=data.get("probabilities", {}),
            audio_info=audio_info,
            model_info=model_info,
            clap_result=clap_result,
            error=data.get("error"),
        )


@dataclass
class CLAPResult:
    """Zero-Shot Genre/Mood-Klassifikation via LAION CLAP."""

    # Scores pro Tag-Set: {"genre": {"metal": 0.42, "pop": 0.18, ...}, "mood": {...}}
    tag_scores: dict = field(default_factory=dict)
    # Top-N Tags über alle Sets (absteigend nach Score sortiert)
    top_tags: list = field(default_factory=list)

    @property
    def genre_scores(self) -> dict:
        return self.tag_scores.get("genre", {})

    @property
    def mood_scores(self) -> dict:
        return self.tag_scores.get("mood", {})

    def top_genre(self) -> Optional[str]:
        """Wahrscheinlichstes Genre oder None wenn keine Genre-Scores vorhanden."""
        scores = self.genre_scores
        return max(scores, key=scores.get) if scores else None

    def top_mood(self) -> Optional[str]:
        """Wahrscheinlichste Stimmung oder None wenn keine Mood-Scores vorhanden."""
        scores = self.mood_scores
        return max(scores, key=scores.get) if scores else None

    def to_dict(self) -> dict:
        return {
            "tag_scores": {
                set_name: {tag: round(score, 4) for tag, score in tags.items()}
                for set_name, tags in self.tag_scores.items()
            },
            "top_tags": self.top_tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CLAPResult":
        return cls(
            tag_scores=data.get("tag_scores", {}),
            top_tags=data.get("top_tags", []),
        )


MEDALS = {0: "\U0001f947", 1: "\U0001f948", 2: "\U0001f949"}  # 🥇🥈🥉
