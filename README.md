# Spotilyzer v2.0 — Hit/Mid/Flop Analyzer

ML-based audio analysis tool. Classifies tracks as **Hit / Mid / Flop** based on mainstream compatibility.

**Pipeline:** Audio file → MERT-v1-330M embeddings (1024-dim) → XGBoost 3-class classifier → GUI or CLI

---

## Quick Start

```bash
# Create & activate venv (Python 3.12 recommended, min. 3.10)
python -m venv .venv312
.\.venv312\Scripts\Activate.ps1   # PowerShell

# Install package
pip install -e .

# Launch GUI
spotilyzer

# CLI — analyze a single track
spotilyzer-cli "my_track.mp3"
```

> **First launch:** MERT-v1-330M (~1.3 GB) is automatically downloaded from HuggingFace
> and cached at `~/.cache/huggingface/hub/`. Internet connection required.

> **Model required:** at least one `models/spotilyzer_model_*.joblib` must be present
> (active model read from `models/active_model.txt`, or newest by mtime as fallback).
> Either train it yourself (see [Training](#training)) or copy a pre-built `.joblib`.

---

## Features

- **GUI** (PySide6): Drag & Drop, three view modes (Simple / Balanced / Pro), Dark/Light theme
- **CLI**: JSON, Minimal or Default output; `--device cuda` for GPU
- **13 analysis fields** per track: Rating, Confidence, Hit/Mid/Flop probabilities + BPM, LUFS, Key, Format, Sample Rate, Bitrate, Channels, Duration, File Size
- **Supported formats:** `.mp3` `.flac` `.wav` `.ogg` `.m4a` `.aac` `.wma`

---

## Model Performance (current)

Trained on **24,170 validated samples** (Deezer 30s previews + Spotify Charts + Kworb historical charts, 12 markets; refreshed 2026-07-13), 1024-dim MERT-v1-330M embeddings. Holdout set: 4,834 samples (20%, each sample = one 30s clip). Production averages chunk probabilities over the full track; song-level evaluation pending.

| Metric            | Value          | Target |
|-------------------|----------------|--------|
| Balanced Accuracy | **64.3 %**     | ≥ 65 % |
| Hit Recall        | **82.4 %** ✓   | ≥ 80 % |
| Flop Recall       | **74.5 %** ✓   | ≥ 50 % |

**Interpretation:** ≥ 85 % confidence = genuine potential. < 60 % = uncertain, treat as Mid.
Inference: ~0.8 s/track on GTX 1660 Ti.

---

## CLI Reference

```bash
# Default output (table)
spotilyzer-cli "track.mp3"

# JSON (machine-readable)
spotilyzer-cli "track.mp3" --style json

# Minimal (rating + score only)
spotilyzer-cli "track.mp3" --style minimal

# Use GPU
spotilyzer-cli "track.mp3" --device cuda

# Without audio info (faster)
spotilyzer-cli "track.mp3" --no-audio-info
```

---

## Setup (Development)

```bash
# Core only
pip install -e .

# With training deps (XGBoost, scikit-learn, transformers, torchaudio …)
pip install -e ".[training]"

# With dev deps (pyinstaller, pytest)
pip install -e ".[dev]"
```

---

## Training

Training runs in the separate repository [SpotilyzerTraining](https://github.com/AndreasV77/SpotilyzerTraining).

**Data sources:**
- **Deezer API** — 30s previews + popularity rank (free, no auth)
- **Last.fm API** — playcount + listeners for label validation
- **Spotify Charts CSV** — Top 200 Charts (manual, 10 markets)
- **Kworb.net** — historical chart data (peak_position, weeks_in_chart)
- **MusicBrainz API** — ISRC lookup for deduplication

**Current dataset:** 24,170 validated samples, 15,980 hits, 23 genre clusters + chart expansion across 12 markets (refreshed 2026-07-13)

**Deployment:**
```powershell
# After training in SpotilyzerTraining:
Copy-Item outputs/models/spotilyzer_model_MERTv1330M_*_validated_*.joblib ..\Spotilyzer\models\
# NOTE: report filenames have no "_validated_" segment (unlike the model .joblib)
Copy-Item outputs/reports/training_report_MERTv1330M_*.json                ..\Spotilyzer\models\
```

---

## Package Structure

```
spotilyzer/          # Installable package
  core/
    pipeline.py      # AnalysisPipeline — orchestrates Embedder + Predictor + AudioInfo
    embedder.py      # MERTEmbedder (Singleton) — MERT-v1-330M, 1024-dim
    predictor.py     # SpotilyzerPredictor — XGBoost wrapper
    audio_info.py    # BPM, LUFS, Key, Format, Waveform
  cli/
    analyze.py       # CLI entry point
  gui/
    app.py           # SpotilyzerApp (QMainWindow)
    central.py       # DropZone + result list + stats
    worker.py        # QThread worker for ML operations
    theme.py         # ThemeManager (Dark/Light + accent color)
    panels/          # Dock panels: file, highscore, history, tech, settings
    widgets/         # DropZone, ResultCard, ConfidenceBar, Waveform
  data/
    models.py        # AnalysisResult, AudioInfo, Rating/AppMode/SortMode
    persistence.py   # JSON/CSV/MD/TXT export, auto-save
  locale/
    EN/
      strings.py     # All English UI strings (localization foundation)
training/            # DEPRECATED — kept for reference only; active training scripts are in SpotilyzerTraining repo
models/              # spotilyzer_model_*.joblib + training_report_*.json (full-named), active_model.txt, model_names.json
resources/           # GUI assets
legacy/              # Archived Spotify API scripts (reference only)
```

---

## Building the Windows EXE

```bash
pip install -e ".[dev]"
pyinstaller spotilyzer.spec

# Remove CUDA libs (~1.5 GB savings)
python strip_cuda.py
```

MERT (~1.3 GB) is **not** bundled — downloaded on first launch.
Total size after strip: ~3 GB.

---

## Known Limitations

- **App icon:** `resources/spotilyzer.ico` missing — window shows default Qt icon
- **Drag & Drop + Admin shell (Windows):** D&D from Explorer doesn't work when the app
  runs in an elevated shell (Windows UIPI). Fix: run app without admin or use the file dialog

---

## Roadmap

**Short-term**
- Create app icon (`resources/spotilyzer.ico`)
- Improve Flop Recall (more Flop samples)
- In-app model download (instead of local training)

**Medium-term**
- "Sounds like ..." — similarity search in embedding space
- Genre classification (second model)
- Genre cluster editor in GUI (PRO mode)

**Long-term**
- Genre-specific models (one per cluster)
