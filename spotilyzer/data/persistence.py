"""
Persistenz & Export - Save/Load + Export in 4 Formate.

Formate:
- JSON: Strukturiert, re-importierbar (Default + Auto-Save)
- CSV:  Tabellarisch, Excel-kompatibel
- MD:   Formatierte Vollausgabe mit Tabelle und Emojis
- TXT:  Plain-Text Vollausgabe (Terminal-Style)
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Optional

from spotilyzer.data.models import AnalysisResult, MEDALS


# ══════════════════════════════════════════════════════════════════════════════
# AUTO-SAVE / LOAD (JSON)
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_SAVE_PATH = Path("spotilyzer_results.json")


def save_results(
    results: list[AnalysisResult],
    path: Path = DEFAULT_SAVE_PATH,
) -> None:
    """Speichert Ergebnisse als JSON (Auto-Save)."""
    data = {
        "version": "2.0",
        "updated": datetime.now().isoformat(),
        "count": len(results),
        "results": [r.to_dict() for r in results],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_results(path: Path = DEFAULT_SAVE_PATH) -> list[AnalysisResult]:
    """
    Lädt gespeicherte Ergebnisse aus JSON.

    Kompatibel mit v1.0 (altes Format ohne audio_info) und v2.0.
    """
    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_results = data.get("results", [])
        return [AnalysisResult.from_dict(r) for r in raw_results]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ══════════════════════════════════════════════════════════════════════════════

class ResultExporter:
    """Exportiert Analyse-Ergebnisse in verschiedene Formate."""

    def __init__(
        self,
        device_info: str = "N/A",
        model_name: str = "spotilyzer_model.joblib",
    ):
        self.device_info = device_info
        self.model_name = model_name

    def to_json(self, results: list[AnalysisResult], path: Path) -> None:
        """Export als JSON (identisch mit Auto-Save Format)."""
        data = {
            "version": "2.0",
            "exported": datetime.now().isoformat(),
            "device": self.device_info,
            "model": self.model_name,
            "count": len(results),
            "results": [r.to_dict() for r in results],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def to_csv(
        self,
        results: list[AnalysisResult],
        path: Path,
        delimiter: str = ";",
    ) -> None:
        """Export als CSV (Excel/Sheets-kompatibel)."""
        valid = [r for r in results if not r.is_error]

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=delimiter)

            # Header
            header = [
                "Datei", "Pfad", "Rating", "Hit%", "Mid%", "Flop%",
                "Konfidenz", "Analysiert", "Modell",
            ]
            # Audio-Info Spalten (falls vorhanden)
            has_audio_info = any(r.audio_info for r in valid)
            if has_audio_info:
                header.extend([
                    "Dauer", "BPM", "LUFS", "Tonart", "Format",
                    "Sample-Rate", "Bitrate", "Channels", "Dateigröße",
                    "Centroid (Hz)", "Flatness", "Onset-Rate (/s)",
                ])
            writer.writerow(header)

            # Daten
            for r in valid:
                model_name = r.model_info.model_name if r.model_info else self.model_name
                row = [
                    r.file,
                    r.path,
                    r.rating.upper(),
                    f"{r.probabilities.get('hit', 0):.1%}",
                    f"{r.probabilities.get('mid', 0):.1%}",
                    f"{r.probabilities.get('flop', 0):.1%}",
                    f"{r.confidence:.1%}",
                    r.timestamp,
                    model_name,
                ]
                if has_audio_info:
                    ai = r.audio_info
                    if ai:
                        row.extend([
                            ai.duration_formatted,
                            f"{ai.bpm:.1f}" if ai.bpm else "",
                            f"{ai.lufs:.1f}" if ai.lufs else "",
                            ai.key or "",
                            ai.format,
                            str(ai.sample_rate),
                            f"{ai.bitrate}" if ai.bitrate else "",
                            ai.channels_label,
                            ai.file_size_formatted,
                            f"{ai.spectral_centroid:.1f}" if ai.spectral_centroid else "",
                            f"{ai.spectral_flatness:.4f}" if ai.spectral_flatness else "",
                            f"{ai.onset_rate:.2f}" if ai.onset_rate else "",
                        ])
                    else:
                        row.extend([""] * 12)
                writer.writerow(row)

    def to_markdown(self, results: list[AnalysisResult], path: Path) -> None:
        """Export als Markdown (menschenlesbar, formatiert)."""
        valid = [r for r in results if not r.is_error]
        now = datetime.now()

        lines = []
        lines.append(f"# \U0001f3b5 Spotilyzer Analyse-Report")
        lines.append(f"")
        lines.append(
            f"**Datum:** {now.strftime('%d.%m.%Y %H:%M')} | "
            f"**Tracks:** {len(valid)} | "
            f"**Device:** {self.device_info}"
        )
        lines.append(f"")

        if not valid:
            lines.append("_Keine Ergebnisse._")
        else:
            # Sortiert nach Hit-Score (absteigend)
            sorted_results = sorted(
                valid,
                key=lambda r: r.probabilities.get("hit", 0),
                reverse=True,
            )

            # Tabelle
            lines.append("## Ergebnisse")
            lines.append("")
            lines.append("| # | Track | Rating | Hit | Mid | Flop | Konfidenz |")
            lines.append("|---|-------|--------|-----|-----|------|-----------|")

            for idx, r in enumerate(sorted_results):
                medal = MEDALS.get(idx, str(idx + 1))
                emoji = {"hit": "\U0001f525", "mid": "\u2796", "flop": "\U0001f480"}.get(r.rating, "?")
                lines.append(
                    f"| {medal} | {r.file} | {emoji} {r.rating.upper()} | "
                    f"{r.probabilities.get('hit', 0):.0%} | "
                    f"{r.probabilities.get('mid', 0):.0%} | "
                    f"{r.probabilities.get('flop', 0):.0%} | "
                    f"{r.confidence:.0%} |"
                )

            # Zusammenfassung
            lines.append("")
            lines.append("## Zusammenfassung")

            best = sorted_results[0]
            hits = sum(1 for r in valid if r.rating == "hit")
            mids = sum(1 for r in valid if r.rating == "mid")
            flops = sum(1 for r in valid if r.rating == "flop")

            lines.append(f"- **Best Track:** {best.file} ({best.hit_probability:.0%} Hit)")
            lines.append(f"- **Hits:** {hits} | **Mids:** {mids} | **Flops:** {flops}")

        lines.append("")
        lines.append(f"---")
        lines.append(f"_Generiert von Spotilyzer v2.0 | Modell: {self.model_name}_")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def to_text(self, results: list[AnalysisResult], path: Path) -> None:
        """Export als Plain-Text (Terminal-Style)."""
        valid = [r for r in results if not r.is_error]
        now = datetime.now()

        lines = []
        sep = "\u2550" * 60
        lines.append(sep)
        lines.append("  SPOTILYZER ANALYSE-REPORT")
        lines.append(
            f"  Datum: {now.strftime('%d.%m.%Y %H:%M')} | "
            f"Tracks: {len(valid)} | "
            f"Device: {self.device_info}"
        )
        lines.append(sep)
        lines.append("")

        if not valid:
            lines.append("  Keine Ergebnisse.")
        else:
            sorted_results = sorted(
                valid,
                key=lambda r: r.probabilities.get("hit", 0),
                reverse=True,
            )

            for idx, r in enumerate(sorted_results):
                medal = MEDALS.get(idx, f"  #{idx + 1}")
                emoji = {"hit": "\U0001f525", "mid": "\u2796", "flop": "\U0001f480"}.get(r.rating, "?")

                lines.append(f"  {medal} {r.file}")
                lines.append(f"     Bewertung:  {emoji} {r.rating.upper()} ({r.confidence:.0%})")
                lines.append(
                    f"     Hit: {r.probabilities.get('hit', 0):.0%} | "
                    f"Mid: {r.probabilities.get('mid', 0):.0%} | "
                    f"Flop: {r.probabilities.get('flop', 0):.0%}"
                )

                # Audio-Info (wenn vorhanden)
                if r.audio_info:
                    ai = r.audio_info
                    info_parts = [f"{ai.duration_formatted}"]
                    if ai.bpm:
                        info_parts.append(f"{ai.bpm:.0f} BPM")
                    if ai.lufs:
                        info_parts.append(f"{ai.lufs:.1f} LUFS")
                    if ai.key:
                        info_parts.append(ai.key)
                    lines.append(f"     Info: {' | '.join(info_parts)}")

                lines.append("")

            # Zusammenfassung
            lines.append("-" * 60)
            best = sorted_results[0]
            hits = sum(1 for r in valid if r.rating == "hit")
            mids = sum(1 for r in valid if r.rating == "mid")
            flops = sum(1 for r in valid if r.rating == "flop")

            lines.append(f"  Best Track: {best.file} ({best.hit_probability:.0%} Hit)")
            lines.append(f"  Hits: {hits} | Mids: {mids} | Flops: {flops}")

        lines.append("")
        lines.append(f"  Spotilyzer v2.0 | Modell: {self.model_name}")
        lines.append(sep)

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
