"""
CLI-Interface für Track-Analyse.

Ersetzt das alte analyze_track.py — nutzt jetzt spotilyzer.core.

Usage:
    python -m spotilyzer.cli.analyze "track.mp3"
    python -m spotilyzer.cli.analyze "track.mp3" --style json --device cuda
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from spotilyzer import SUPPORTED_FORMATS
from spotilyzer.core.pipeline import AnalysisPipeline
from spotilyzer.data.models import AnalysisResult


DEFAULT_MODEL_PATH = Path("models/spotilyzer_model.joblib")


def print_result(result: AnalysisResult, style: str = "default") -> None:
    """Gibt das Analyse-Ergebnis formatiert aus."""

    if result.is_error:
        print(f"\n  \u274c Fehler: {result.error}")
        return

    rating = result.rating.upper()
    conf = result.confidence
    probs = result.probabilities

    emoji = {"HIT": "\U0001f525", "MID": "\u2796", "FLOP": "\U0001f480"}.get(rating, "?")

    if style == "minimal":
        print(f"{result.file}: {rating} ({conf:.0%})")
        return

    if style == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    # Default: Box-Format
    bar_len = 20
    filled = int(conf * bar_len)
    bar = "\u2588" * filled + "\u2591" * (bar_len - filled)

    output = f"""
\u2554{'=' * 79}
\u2551  SPOTILYZER ANALYSIS
\u2560{'=' * 79}
\u2551  Track:       {result.file[:50]}
\u2551
\u2551  Bewertung:   {emoji} {rating}
\u2551  Konfidenz:   [{bar}] {conf:.1%}
\u2551
\u2551  Wahrscheinlichkeiten:
\u2551    \U0001f525 Hit:    {probs.get('hit', 0):>6.1%}
\u2551    \u2796 Mid:    {probs.get('mid', 0):>6.1%}
\u2551    \U0001f480 Flop:   {probs.get('flop', 0):>6.1%}"""

    # Audio-Info (wenn vorhanden)
    if result.audio_info:
        ai = result.audio_info
        output += f"""
\u2551
\u2551  Technische Daten:
\u2551    Dauer:       {ai.duration_formatted}
\u2551    Format:      {ai.format.upper()} | {ai.sample_rate} Hz | {ai.channels_label}"""
        if ai.bpm:
            output += f"\n\u2551    Tempo:       {ai.bpm:.1f} BPM"
        if ai.lufs:
            output += f"\n\u2551    Lautheit:    {ai.lufs:.1f} LUFS"
        if ai.key:
            output += f"\n\u2551    Tonart:      {ai.key}"
        if ai.bitrate:
            output += f"\n\u2551    Bitrate:     {ai.bitrate} kbps"

    # CLAP-Ergebnis (wenn vorhanden)
    if result.clap_result:
        clap = result.clap_result
        output += "\n\u2551\n\u2551  Genre / Mood (CLAP Zero-Shot):"
        if clap.genre_scores:
            top_genre = clap.top_genre()
            top_score = clap.genre_scores.get(top_genre, 0)
            output += f"\n\u2551    Genre:       {top_genre} ({top_score:.3f})"
        if clap.mood_scores:
            top_mood = clap.top_mood()
            top_score = clap.mood_scores.get(top_mood, 0)
            output += f"\n\u2551    Stimmung:    {top_mood} ({top_score:.3f})"
        if clap.top_tags:
            output += f"\n\u2551    Top Tags:    {', '.join(clap.top_tags)}"

    output += f"\n\u255a{'=' * 79}\n"
    print(output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analysiere einen Track auf Hit-Potenzial",
        prog="spotilyzer",
    )
    parser.add_argument(
        "track",
        type=str,
        help="Pfad zur Audio-Datei (MP3, WAV, FLAC, etc.)",
    )
    parser.add_argument(
        "--model",
        default=str(DEFAULT_MODEL_PATH),
        help=f"Pfad zum trainierten Modell (default: {DEFAULT_MODEL_PATH})",
    )
    parser.add_argument(
        "--style",
        choices=["default", "minimal", "json"],
        default="default",
        help="Output-Stil (default: default)",
    )
    parser.add_argument(
        "--device",
        choices=["cuda", "cpu", "auto"],
        default="auto",
        help="Device für MERT (default: auto)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Weniger Output während Verarbeitung",
    )
    parser.add_argument(
        "--no-audio-info",
        action="store_true",
        help="Keine technischen Audio-Daten extrahieren",
    )
    parser.add_argument(
        "--include-clap",
        action="store_true",
        help="Zero-Shot Genre/Mood-Analyse via LAION CLAP (lädt ~600 MB Modell)",
    )
    parser.add_argument(
        "--vram-mode",
        choices=["parallel", "sequential"],
        default="parallel",
        help="VRAM-Modus: parallel (Standard) oder sequential (für <8 GB VRAM)",
    )
    args = parser.parse_args()

    track_path = Path(args.track)
    model_path = Path(args.model)

    # Validierung
    if not track_path.exists():
        print(f"Fehler: Datei nicht gefunden: {track_path}", file=sys.stderr)
        sys.exit(1)

    if track_path.suffix.lower() not in SUPPORTED_FORMATS:
        print(
            f"Fehler: Nicht unterstütztes Format: {track_path.suffix}\n"
            f"Unterstützt: {', '.join(sorted(SUPPORTED_FORMATS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not model_path.exists():
        print(f"Fehler: Modell nicht gefunden: {model_path}", file=sys.stderr)
        print(f"\u2192 Erst 'python training/train_model.py' ausführen!", file=sys.stderr)
        sys.exit(1)

    # Pipeline initialisieren
    progress = None if args.quiet else lambda msg: print(f"  {msg}")

    try:
        pipeline = AnalysisPipeline(
            model_path=model_path,
            device=args.device,
            progress_callback=progress,
            vram_mode=args.vram_mode,
        )
    except Exception as e:
        print(f"Fehler beim Laden der Pipeline: {e}", file=sys.stderr)
        sys.exit(1)

    # Analyse
    if not args.quiet:
        print(f"\n  Analysiere: {track_path.name}")

    result = pipeline.analyze(
        track_path,
        include_audio_info=not args.no_audio_info,
        include_clap=args.include_clap,
    )

    # Output
    print_result(result, style=args.style)

    # Exit-Code basierend auf Ergebnis
    if result.is_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
