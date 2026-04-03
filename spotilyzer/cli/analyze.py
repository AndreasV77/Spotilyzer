"""
CLI-Interface f\u00fcr Track-Analyse.

Ersetzt das alte analyze_track.py \u2014 nutzt jetzt spotilyzer.core.

Usage:
    python -m spotilyzer.cli.analyze "track.mp3"
    python -m spotilyzer.cli.analyze "track.mp3" --style json --device cuda
    python -m spotilyzer.cli.analyze "track.mp3" --full-analysis
    python -m spotilyzer.cli.analyze "track.mp3" --full-analysis --no-rating
    python -m spotilyzer.cli.analyze "folder/" --threesome
    python -m spotilyzer.cli.analyze "*.mp3" --threesome > report.txt
"""

from __future__ import annotations

import argparse
import glob as _glob
import json
import math
import sys
from pathlib import Path

from spotilyzer import SUPPORTED_FORMATS
from spotilyzer.core.pipeline import AnalysisPipeline
from spotilyzer.data.models import AnalysisResult
from spotilyzer.analysis import FeatureExtractor, SpectralAnalysisResult


def _find_default_model() -> Path:
    """Neuestes spotilyzer_model_*.joblib in models/; Fallback auf legacy-Name."""
    models_dir = Path("models")
    found = sorted(
        models_dir.glob("spotilyzer_model_*.joblib"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return found[0] if found else models_dir / "spotilyzer_model.joblib"


DEFAULT_MODEL_PATH = _find_default_model()


def _resolve_tracks(pattern: str) -> list[Path]:
    """
    L\u00f6st ein Track-Argument zu einer Liste von Audio-Pfaden auf.

    Akzeptiert:
      - Einzelne Datei:   "track.mp3"
      - Ordner:           "D:/Music/Gabber/"   (alle unterst\u00fctzten Formate, nicht-rekursiv)
      - Glob-Pattern:     "*.mp3"  /  "**/*.flac"
      - Mehrere Pfade:    Wird von argparse (nargs="+") als Liste \u00fcbergeben
    """
    p = Path(pattern)

    # Ordner → alle unterst\u00fctzten Audio-Dateien (1 Ebene)
    if p.is_dir():
        paths: list[Path] = []
        for fmt in SUPPORTED_FORMATS:
            paths.extend(p.glob(f"*{fmt}"))
        return sorted(set(paths))

    # Glob-Pattern expandieren
    matches = _glob.glob(pattern, recursive=True)
    if matches:
        return sorted(
            Path(m) for m in matches
            if Path(m).is_file() and Path(m).suffix.lower() in SUPPORTED_FORMATS
        )

    # Einzelne Datei (existiert oder nicht — Validierung sp\u00e4ter)
    return [p]


# ── Threesome (BPM / LUFS / PLR) ─────────────────────────────────────────────

def _plr(lufs: float | None, true_peak: float | None) -> float | None:
    """Peak-to-Loudness Ratio = True Peak (dBFS) \u2212 Integrated LUFS."""
    if lufs is not None and true_peak is not None:
        return round(true_peak - lufs, 1)
    return None


def print_threesome(tracks: list[Path], quiet: bool = False) -> None:
    """
    Batch-Ausgabe der heiligen Dreifaltigkeit: BPM | LUFS | PLR + Dynamic Range.
    Kein ML-Modell ben\u00f6tigt.  Perfekt f\u00fcr Pipe in .txt.
    """
    from spotilyzer.core.audio_info import extract_audio_info

    # Spaltenbreiten
    name_w = min(50, max((len(t.name) for t in tracks), default=20))
    header = (
        f"{'Track':<{name_w}}  {'BPM':>7}  {'LUFS':>7}  {'TruePeak':>9}  "
        f"{'PLR':>6}  {'Key':<10}  {'Duration':>8}"
    )
    sep = "-" * len(header)

    print(header)
    print(sep)

    errors: list[str] = []

    for track in tracks:
        if not track.exists():
            errors.append(f"Nicht gefunden: {track}")
            continue
        if track.suffix.lower() not in SUPPORTED_FORMATS:
            errors.append(f"Format nicht unterst\u00fctzt: {track.name}")
            continue

        if not quiet:
            print(f"  \u2026 {track.name}", end="\r", file=sys.stderr)

        try:
            ai = extract_audio_info(track)
        except Exception as e:
            errors.append(f"Fehler bei {track.name}: {e}")
            continue

        bpm_s    = f"{ai.bpm:>7.1f}"      if ai.bpm            else f"{'–':>7}"
        lufs_s   = f"{ai.lufs:>7.1f}"     if ai.lufs           else f"{'–':>7}"
        peak_s   = f"{ai.true_peak_dbfs:>9.1f}" if ai.true_peak_dbfs is not None else f"{'–':>9}"
        plr      = _plr(ai.lufs, ai.true_peak_dbfs)
        plr_s    = f"{plr:>6.1f}"         if plr  is not None  else f"{'–':>6}"
        key_s    = f"{ai.key:<10}"         if ai.key            else f"{'–':<10}"
        dur_s    = f"{ai.duration_formatted:>8}"

        name_trunc = track.name[:name_w]
        print(f"{name_trunc:<{name_w}}  {bpm_s}  {lufs_s}  {peak_s}  {plr_s}  {key_s}  {dur_s}")

    # Leerzeile + Fehler ans Ende
    if errors:
        print()
        for e in errors:
            print(f"  \u26a0  {e}", file=sys.stderr)

    if not quiet:
        # Terminal-Zeile s\u00e4ubern (falls \u2026-Fortschritt gezeigt wurde)
        print(" " * 60, end="\r", file=sys.stderr)


# Box-Zeichensatz
_W = 79
_TL = "\u2554"   # \u2554
_TR = "\u2557"   # \u2557
_BL = "\u255a"   # \u255a
_BR = "\u255d"   # \u255d
_H  = "\u2550"   # \u2550
_V  = "\u2551"   # \u2551
_ML = "\u2560"   # \u2560
_MR = "\u2563"   # \u2563
_DL = "\u255f"   # \u255f (leichte Trennlinie links)
_DR = "\u2562"   # \u2562
_LH = "\u2500"   # \u2500 (leichte horizontale Linie)


# \u2500\u2500 Ausgabe-Hilfsfunktionen \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _box_top(title: str = "") -> str:
    if title:
        pad = _W - 2 - len(title)
        return f"{_TL}{_H} {title} {_H * pad}{_TR}"
    return f"{_TL}{_H * _W}{_TR}"

def _box_sep(label: str = "") -> str:
    if label:
        pad = _W - 4 - len(label)
        return f"{_DL}{_LH}\u2500 {label} {_LH * max(pad, 0)}{_DR}"
    return f"{_ML}{_H * _W}{_MR}"

def _box_line(text: str = "") -> str:
    return f"{_V}  {text}"

def _box_bot() -> str:
    return f"{_BL}{_H * _W}{_BR}"


def print_spectral(spectral: SpectralAnalysisResult) -> None:
    """Gibt die vollst\u00e4ndige Spektral-/Rollen-Analyse formatiert aus."""
    print(_box_sep("SPEKTRAL-ANALYSE"))

    for line in spectral.to_ki_context().splitlines():
        if line.startswith("==="):
            label = line.strip("= ").strip()
            print(_box_sep(label))
        elif line:
            # Lange Zeilen k\u00fcrzen
            display = line if len(line) <= _W - 2 else line[:_W - 5] + "\u2026"
            print(_box_line(display))
        else:
            print(_box_line())

    print(_box_bot())
    print()


def print_spectral_only(spectral: SpectralAnalysisResult, style: str,
                        track_name: str) -> None:
    """Reine Spektral-Ausgabe ohne ML-Rating (f\u00fcr --no-rating)."""
    if style == "json":
        print(json.dumps(
            {"track": track_name, "spectral_analysis": spectral.to_dict()},
            indent=2, ensure_ascii=False,
        ))
        return

    if style == "minimal":
        tm = spectral.temporal
        pr = spectral.production
        parts = [track_name]
        if bpm := tm.get("bpm"):
            parts.append(f"BPM={bpm.raw_value}")
        if lufs := pr.get("lufs"):
            parts.append(f"LUFS={lufs.raw_value:.1f}")
        if roles := spectral.roles:
            if roles.dominant_roles:
                parts.append(roles.dominant_roles[0])
        print("  ".join(parts))
        return

    # Default
    print()
    print(_box_top("SPOTILYZER \u2014 SPEKTRAL-ANALYSE"))
    print(_box_line(f"Track:  {track_name[:60]}"))
    print_spectral(spectral)


def print_result(result: AnalysisResult, style: str = "default",
                 spectral: SpectralAnalysisResult | None = None) -> None:
    """Gibt das Analyse-Ergebnis formatiert aus."""

    if result.is_error:
        print(f"\n  \u274c Fehler: {result.error}")
        return

    rating = result.rating.upper()
    conf = result.confidence
    probs = result.probabilities

    emoji = {"HIT": "\U0001f525", "MID": "\u2796", "FLOP": "\U0001f480"}.get(rating, "?")

    if style == "minimal":
        line = f"{result.file}: {rating} ({conf:.0%})"
        if spectral:
            tm = spectral.temporal
            if bpm := tm.get("bpm"):
                line += f"  BPM={bpm.raw_value}"
        print(line)
        return

    if style == "json":
        d = result.to_dict()
        if spectral:
            d["spectral_analysis"] = spectral.to_dict()
        print(json.dumps(d, indent=2, ensure_ascii=False))
        return

    # Default: Box-Format
    bar_len = 20
    filled = int(conf * bar_len)
    bar = "\u2588" * filled + "\u2591" * (bar_len - filled)

    print()
    print(_box_top("SPOTILYZER ANALYSIS"))
    print(_box_line(f"Track:       {result.file[:60]}"))
    print(_box_line())
    print(_box_line(f"Bewertung:   {emoji} {rating}"))
    print(_box_line(f"Konfidenz:   [{bar}] {conf:.1%}"))
    print(_box_line())
    print(_box_sep("Wahrscheinlichkeiten"))
    print(_box_line(f"  \U0001f525 Hit:    {probs.get('hit', 0):>6.1%}"))
    print(_box_line(f"  \u2796 Mid:    {probs.get('mid', 0):>6.1%}"))
    print(_box_line(f"  \U0001f480 Flop:   {probs.get('flop', 0):>6.1%}"))

    # Audio-Info
    if result.audio_info:
        ai = result.audio_info
        print(_box_sep("Technische Daten"))
        print(_box_line(f"  Dauer:       {ai.duration_formatted}"))
        print(_box_line(f"  Format:      {ai.format.upper()} | {ai.sample_rate} Hz | {ai.channels_label}"))
        if ai.bpm:
            print(_box_line(f"  Tempo:       {ai.bpm:.1f} BPM"))
        if ai.lufs:
            print(_box_line(f"  Lautheit:    {ai.lufs:.1f} LUFS"))
        if ai.key:
            print(_box_line(f"  Tonart:      {ai.key}"))
        if ai.bitrate:
            print(_box_line(f"  Bitrate:     {ai.bitrate} kbps"))

    # CLAP
    if result.clap_result:
        clap = result.clap_result
        print(_box_sep("Genre / Mood (CLAP Zero-Shot)"))
        if clap.genre_scores:
            top_genre = clap.top_genre()
            top_score = clap.genre_scores.get(top_genre, 0)
            print(_box_line(f"  Genre:       {top_genre} ({top_score:.3f})"))
        if clap.mood_scores:
            top_mood = clap.top_mood()
            top_score = clap.mood_scores.get(top_mood, 0)
            print(_box_line(f"  Stimmung:    {top_mood} ({top_score:.3f})"))
        if clap.top_tags:
            print(_box_line(f"  Top Tags:    {', '.join(clap.top_tags)}"))

    # Spektral-Analyse (nahtlos angef\u00fcgt, kein extra Box-Bottom vorher)
    if spectral:
        print_spectral(spectral)
    else:
        print(_box_bot())
        print()


# \u2500\u2500 main \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analysiere einen Track auf Hit-Potenzial",
        prog="spotilyzer",
    )
    parser.add_argument(
        "track",
        type=str,
        nargs="+",
        help=(
            "Pfad(e) zur Audio-Datei, Ordner oder Glob-Pattern. "
            "Beispiele: track.mp3 | folder/ | *.flac | **/*.mp3"
        ),
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
        help="Device f\u00fcr MERT (default: auto)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Weniger Output w\u00e4hrend Verarbeitung",
    )
    parser.add_argument(
        "--no-audio-info",
        action="store_true",
        help="Keine technischen Audio-Daten extrahieren",
    )
    parser.add_argument(
        "--include-clap",
        action="store_true",
        help="Zero-Shot Genre/Mood-Analyse via LAION CLAP (l\u00e4dt ~600 MB Modell)",
    )
    parser.add_argument(
        "--vram-mode",
        choices=["parallel", "sequential"],
        default="parallel",
        help="VRAM-Modus: parallel (Standard) oder sequential (f\u00fcr <8 GB VRAM)",
    )
    parser.add_argument(
        "--full-analysis",
        action="store_true",
        help=(
            "Vollst\u00e4ndige Spektral-/Rollen-Analyse (librosa Phase 1+2). "
            "Zeigt Spektrum, Rhythmus, Produktion, Mix-Diagnose und Instrument-Rollen."
        ),
    )
    parser.add_argument(
        "--no-rating",
        action="store_true",
        help=(
            "Nur Spektral-Analyse, kein ML-Rating. "
            "Ben\u00f6tigt kein Modell. Impliziert --full-analysis."
        ),
    )
    parser.add_argument(
        "--threesome",
        action="store_true",
        help=(
            "Batch-Modus: BPM | LUFS | True Peak | PLR pro Track als Tabelle. "
            "Kein Modell ben\u00f6tigt. Unterst\u00fctzt Ordner, Globs und mehrere Pfade. "
            "Perfekt f\u00fcr Pipe: --threesome > report.txt"
        ),
    )
    args = parser.parse_args()

    # --no-rating impliziert --full-analysis
    if args.no_rating:
        args.full_analysis = True

    # ── Tracks aufl\u00f6sen ────────────────────────────────────────────────────────
    all_tracks: list[Path] = []
    for pattern in args.track:
        all_tracks.extend(_resolve_tracks(pattern))

    # Duplikate entfernen, Reihenfolge beibehalten
    seen: set[Path] = set()
    tracks: list[Path] = []
    for t in all_tracks:
        if t not in seen:
            seen.add(t)
            tracks.append(t)

    # ── --threesome: Batch-Tabelle ────────────────────────────────────────────
    if args.threesome:
        if not tracks:
            print("Fehler: Keine Audio-Dateien gefunden.", file=sys.stderr)
            sys.exit(1)
        print_threesome(tracks, quiet=args.quiet)
        return

    # ── Einzeltrack-Modi: genau einen Track erwartet ─────────────────────────
    if len(tracks) > 1:
        print(
            f"Fehler: Mehrere Tracks ({len(tracks)}) ohne --threesome angegeben.\n"
            f"\u2192 F\u00fcr Batch-Analyse: --threesome",
            file=sys.stderr,
        )
        sys.exit(1)

    if not tracks:
        print("Fehler: Keine Audio-Datei gefunden.", file=sys.stderr)
        sys.exit(1)

    track_path = tracks[0]
    model_path = Path(args.model)

    # Validierung: Track
    if not track_path.exists():
        print(f"Fehler: Datei nicht gefunden: {track_path}", file=sys.stderr)
        sys.exit(1)

    if track_path.suffix.lower() not in SUPPORTED_FORMATS:
        print(
            f"Fehler: Nicht unterst\u00fctztes Format: {track_path.suffix}\n"
            f"Unterst\u00fctzt: {', '.join(sorted(SUPPORTED_FORMATS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validierung: Modell (nur wenn Rating gew\u00fcnscht)
    need_model = not args.no_rating
    if need_model and not model_path.exists():
        print(f"Fehler: Modell nicht gefunden: {model_path}", file=sys.stderr)
        if args.full_analysis:
            print(
                "\u2192 Tipp: Mit --no-rating kannst du die Spektral-Analyse ohne Modell ausf\u00fchren.",
                file=sys.stderr,
            )
        else:
            print(f"\u2192 Erst 'python training/train_model.py' ausf\u00fchren!", file=sys.stderr)
        sys.exit(1)

    progress = None if args.quiet else lambda msg: print(f"  {msg}")

    # \u2500\u2500 Spektral-Analyse (Phase 1+2) ──────────────────────────────────────────
    spectral: SpectralAnalysisResult | None = None
    if args.full_analysis:
        if not args.quiet:
            print(f"\n  Spektral-Analyse: {track_path.name}")
        try:
            spectral = FeatureExtractor().extract(track_path)
        except Exception as e:
            print(f"Warnung: Spektral-Analyse fehlgeschlagen: {e}", file=sys.stderr)
            spectral = None

    # \u2500\u2500 Nur Spektral (--no-rating) ──────────────────────────────────────────────
    if args.no_rating:
        if spectral is None:
            sys.exit(1)
        print_spectral_only(spectral, style=args.style, track_name=track_path.name)
        return

    # \u2500\u2500 ML-Pipeline ─────────────────────────────────────────────────────────────
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

    if not args.quiet:
        print(f"\n  Analysiere: {track_path.name}")

    result = pipeline.analyze(
        track_path,
        include_audio_info=not args.no_audio_info,
        include_clap=args.include_clap,
    )

    print_result(result, style=args.style, spectral=spectral)

    if result.is_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
