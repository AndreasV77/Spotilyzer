# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Spotilyzer (v2.0) is an ML-based audio analysis tool that classifies tracks as **Hit / Mid / Flop** based on mainstream compatibility. Pipeline: audio file → MERT-v1-95M embeddings (768-dim) → XGBoost 3-class classifier → GUI or CLI output.

The PySide6 GUI rewrite (from Tkinter) was designed around three pillars:
- **Three view modes**: Simple (drop zone only) / Balanced (default) / Pro (all dock panels)
- **Three UX tiers** (AppMode): same modes, control visibility of fields and features throughout
- **13 analysis fields per track**: rating, confidence, probabilities + 10 technical fields (BPM, LUFS, key, format, sample rate, bitrate, channels, duration, file size, energy)

Optional CLAP layer (zero-shot, per-request): genre + mood tags via `laion/larger_clap_music`.

## Setup

- **Python**: 3.12 (dev env); minimum 3.10 per `pyproject.toml`; venv at `.venv-spotilyzer/`
- **Activate**: `.\.venv-spotilyzer\Scripts\Activate.ps1` (PowerShell)
- **Install core**: `pip install -e .` (run from repo root)
- **Install with training deps**: `pip install -e ".[training]"`
- **Install with dev deps**: `pip install -e ".[dev]"` (adds pyinstaller, pytest)
- **Model required**: `models/spotilyzer_model.joblib` must exist before running — train it or copy it
- **MERT model** (~380 MB): auto-downloaded by HuggingFace `transformers` on first run to `~/.cache/huggingface/hub/`
- **CLAP model** (~776 MB): auto-downloaded on first `--include-clap` run to `~/.cache/huggingface/hub/`

## Common Commands

```bash
# Run GUI
python main.py
# Or, after pip install:
spotilyzer          # GUI entry point
spotilyzer-gui      # Alias for GUI entry point

# CLI — analyze a single track
python -m spotilyzer.cli.analyze "track.mp3"
python -m spotilyzer.cli.analyze "track.mp3" --style json --device cuda
python -m spotilyzer.cli.analyze "track.mp3" --style minimal --no-audio-info
python -m spotilyzer.cli.analyze "track.mp3" --include-clap --vram-mode sequential
# Or, after pip install (IMPORTANT: run from worktree dir, not main repo root):
spotilyzer-cli "track.mp3" --include-clap --vram-mode sequential

# Training pipeline (run in order)
python training/extract_embeddings.py       # Audio → embeddings/embeddings.npy + embeddings_meta.csv
python training/train_model.py              # → models/spotilyzer_model.joblib + models/training_report.json

# Build standalone Windows EXE
pyinstaller spotilyzer.spec
# After build, strip unnecessary CUDA libs (~1.5 GB savings):
python strip_cuda.py
```

**⚠ Dev-Worktree caveat**: The editable install's package lookup is shadowed by the main repo's `spotilyzer/` directory if Python is invoked from `G:\Dev\Source\Spotilyzer\`. Always `cd` into the worktree before using `-m spotilyzer.cli.analyze`.

## Package Architecture

```
spotilyzer/              # installable package (pyproject.toml), version 2.0.0
  __init__.py            # SUPPORTED_FORMATS, MERT_MODEL_NAME="m-a-p/MERT-v1-95M",
                         # CLAP_MODEL_NAME="laion/larger_clap_music",
                         # TARGET_SAMPLE_RATE=24000, MAX_AUDIO_LENGTH_SEC=30
  core/
    pipeline.py          # AnalysisPipeline — orchestrates Embedder + Predictor + AudioInfo + CLAP
    embedder.py          # MERTEmbedder (singleton) — loads MERT, extracts 768-dim embeddings
    predictor.py         # SpotilyzerPredictor — wraps XGBoost model (.joblib dict)
    audio_info.py        # extract_audio_info(), extract_waveform_display(); LUFS via pyloudnorm
    clap_analyzer.py     # CLAPAnalyzer (singleton) — zero-shot genre/mood via LAION CLAP
  cli/
    analyze.py           # CLI entry; --style default|minimal|json, --include-clap, --vram-mode
  gui/
    app.py               # SpotilyzerApp (QMainWindow) — central coordinator, all wiring
    central.py           # CentralWidget — DropZone + result list + stats bar
    worker.py            # QThread workers: PipelineInitWorker, AnalysisWorker, WaveformWorker
    theme.py             # ThemeManager — generates QSS for Dark/Light + accent color
    panels/              # QDockWidgets: file_panel, highscore_panel, history_panel,
                         #               tech_panel (waveform + audio preview), settings_panel
    widgets/             # dropzone.py, result_card.py, confidence_bar.py, waveform.py
  data/
    models.py            # AnalysisResult, AudioInfo, ModelInfo, CLAPResult,
                         # Rating/AppMode/SortMode enums
    persistence.py       # save_results(), load_results(), ResultExporter (JSON/CSV/MD/TXT)
training/                # not bundled in exe
  extract_embeddings.py  # batch MERT embedding extraction
  train_model.py         # XGBoost training
  download_previews.py   # download Deezer 30s previews for training data
  scout_genre_clusters_deezer.py  # scout reference tracks, build rank labels
legacy/                  # archived old Spotify-API-based scripts (read-only reference)
resources/               # GUI assets (icons, images)
models/                  # spotilyzer_model.joblib + training_report.json (bundled in exe)
# Root-level legacy files (NOT part of the package, kept for reference):
analyze_track.py         # legacy standalone CLI (predates spotilyzer.cli package)
spotilyzer_gui.py        # legacy Tkinter GUI (predates PySide6 rewrite)
```

## Key Design Decisions

**MERTEmbedder is a singleton** (`MERTEmbedder.get_instance()`). Loading is slow — it stays in memory for the session. Call `MERTEmbedder.reset_instance()` in tests to reset.

**CLAPAnalyzer is a singleton** (`CLAPAnalyzer.get_instance()`). Same pattern as MERTEmbedder. Only loaded when `include_clap=True` is passed to `AnalysisPipeline.analyze()`. Call `CLAPAnalyzer.reset_instance()` in tests.

**Sequential VRAM mode** (`vram_mode="sequential"`): For 6 GB GPUs — MERT offloads to CPU before CLAP loads to GPU and vice versa. Both models have `offload_to_cpu()` / `restore_to_device()` / `_ensure_on_device()` methods. Default `vram_mode="concurrent"` keeps both on GPU simultaneously.

**CLAP tag sets**: `DEFAULT_TAG_SETS` in `clap_analyzer.py` defines genre and mood tag lists. Custom tag sets can be passed via `clap_tag_sets` parameter. Metal subgenres ("gothic metal", "doom metal", etc.) should be added for better accuracy on heavy music.

**Model file format**: `models/spotilyzer_model.joblib` is a `dict` with keys `"model"` (XGBoost) and `"label_encoder"` (sklearn LabelEncoder). The optional `models/training_report.json` provides metadata shown in the GUI.

**Audio preprocessing**: mono conversion → resample to 24 kHz → clip to center 30 seconds before embedding.

**LUFS measurement**: `_estimate_lufs()` in `audio_info.py` uses `pyloudnorm` for full EBU R128 (K-weighting + 400ms block gating). Falls back to RMS→dBFS approximation if pyloudnorm unavailable.

**GUI threading**: all ML work runs in QThread workers (`worker.py`). Pipeline initializes 100ms after startup via `QTimer.singleShot`. Never call pipeline methods from the main thread.

**Three-tier UX (AppMode)**: all 13 analysis fields are always computed — the tier only controls visibility. `SIMPLE` hides all dock panels; `BALANCED` shows highscore, history, tech panels; `PRO` shows all panels including file browser and settings.

**Result card grid-snap**: Implemented. `ResultCard` uses `CARD_HEIGHTS = {SIMPLE: 68, BALANCED: 88, PRO: 88}` with `setFixedHeight()`. `CentralWidget.resizeEvent` calls `_adjust_results_viewport()` to snap the visible area to a multiple of card height. Scroll step is set to card height. DropZone collapses to 50 px (compact mode) when results are present.

**Auto-save**: results persist to `spotilyzer_results.json` in CWD after each batch. Loaded automatically on startup. Format version `"2.0"`.

**Model search order** (GUI): `models/spotilyzer_model.joblib` → project root → `~/.spotilyzer/models/` → PyInstaller bundle (`sys._MEIPASS`).

**Audio preview**: `QMediaPlayer` + `QAudioOutput` from `PySide6.QtMultimedia`. Supports MP3, FLAC, WAV, OGG via Windows Media Foundation backend.

**Layout persistence**: dock panel positions saved/restored via `QSettings.saveState()` / `restoreState()`. Organization: `"Spotilyzer"`, App: `"Spotilyzer"`.

**Packaging**: PyInstaller `--onedir` via `spotilyzer.spec`. MERT and CLAP (~380 MB / ~776 MB) are NOT bundled — downloaded on first run. After build, `strip_cuda.py` removes unused CUDA DLLs saving ~1.5 GB. Total bundled size ~3 GB.

## Intended Usage Profile

**Batch size**: typically 1–10 tracks per session, rarely more. No streaming/bulk-pipeline requirements.
**Latency tolerance**: a few seconds per track is fine; throughput optimization is low priority.
**Training**: runs overnight unattended — hours-long GPU jobs are acceptable.
**Hardware target**: Windows PC with GTX 1660 Ti (6 GB VRAM), 16–32 GB RAM. CPU-only fallback must work but can be slower.
**Model upgrades** (e.g., MERT-330M): justified by quality gains, not speed — retrain in SpotilyzerTraining, swap `.joblib`.

This profile means: **quality over speed**, **correctness over throughput**, **single-user desktop app**.

## Supported Audio Formats

`.mp3`, `.flac`, `.wav`, `.ogg`, `.m4a`, `.aac`, `.wma`

## torchaudio Backend (⚠ torchaudio ≥ 2.5)

torchaudio ≥ 2.5 defaults to the `torchcodec` backend which requires the separate `torchcodec` package. We do **not** install torchcodec. All `torchaudio.load()` calls use a soundfile-first fallback pattern:

```python
try:
    waveform, sr = torchaudio.load(str(path), backend="soundfile")
except Exception:
    waveform, sr = torchaudio.load(path)  # last resort
```

This pattern is applied in `embedder.py`, `audio_info.py`, and `clap_analyzer.py`. `soundfile` is listed as a core dependency in `pyproject.toml`.

## Model Performance (current)

Trained on **5,600 samples** (4,789 Deezer 30s previews + charts), 768-dim MERT embeddings.

| Metric | Value |
|--------|-------|
| Accuracy | 71.0% |
| Balanced Accuracy | 62.5% |
| F1 macro | 64.8% |
| Hit Recall | **93.6%** (strong) |
| Flop Recall | 26.8% (weak — many Flops misclassified as Hits) |
| Mid Precision | 94.1% (strong) |

**Model bias:** Defaults to "Hit" under uncertainty. Practical interpretation: 85%+ confidence = genuine potential; below 60% = treat as uncertain. Deezer rank thresholds: Flop < 300k, Mid 300k–700k, Hit > 700k.

**Inference speed:** ~0.53s/track on GTX 1660 Ti.

## Training Data & Genre Clusters

**Why Deezer, not Spotify:** Spotify removed `/audio-features`, track `popularity`, artist `popularity/followers`, and the Recommendations API in Feb 2026. Deezer provides a free unauthenticated API with a `rank` field as popularity proxy and working preview URLs (unlike Spotify in DE/GEMA regions).

**Deezer caveat:** Preview URLs expire in ~15 min — `download_previews.py` fetches fresh URLs at download time. Deezer's genre/related-artist endpoints are unreliable; seed-artist lists per cluster are used.

**16 Genre Clusters** (with seed artists in `scout_genre_clusters_deezer.py`):
Extreme Metal, Gothic, Heavy Metal, Power/Symphonic, Modern Metal, Metalcore, Crossover, Hard Rock, Mainstream Rock, Modern Rock, Classic/Southern Rock, Alternative, Punk, Hardcore, Trance, House.

Country charts (DE, US, UK, JP, GLOBAL) add ~500 extra tracks to training data.

## Training Data Flow

1. `training/scout_genre_clusters_deezer.py` → `scout_results_deezer/scouted_tracks.csv`
2. `training/download_previews.py` → `previews/` (~4,789 MP3s, ~2.2 GB)
3. `training/extract_embeddings.py` → `embeddings/embeddings.npy` [N×768] + `embeddings_meta.csv`
4. `training/train_model.py` → `models/spotilyzer_model.joblib` + `models/training_report.json`

## Known Issues & Gotchas

**App icon missing:** `resources/spotilyzer.ico` does not exist yet. The `spotilyzer.spec` conditionally includes it if present — the build works without it, but the window and taskbar will show the default Qt icon.

**Drag & Drop + admin shell (Windows UIPI):** D&D from Explorer does not work when the app runs in an elevated terminal. Run `python main.py` from a non-admin shell, or use the file-open dialog instead.

**PySide6 enum/string coercion:** `QComboBox.currentData()` and `QSettings.value()` return plain strings, not Python enum instances. The codebase guards against this (e.g., `AppMode(str(mode))` in `app.py`, `settings_panel.py`). Don't assume signal payloads are always enum instances when adding new signal connections.

**MERT first-run download:** ~380 MB, requires internet, cached at `~/.cache/huggingface/hub/models--m-a-p--MERT-v1-95M/`.

**CLAP first-run download:** ~776 MB, cached at `~/.cache/huggingface/hub/models--laion--larger_clap_music/`.

**MERT loads on CPU despite CUDA being available:** Likely a `torch` CPU-only wheel in the venv. Verify with `python -c "import torch; print(torch.cuda.is_available())"`. Reinstall with CUDA-enabled torch if needed.

**CLAP genre accuracy on niche genres:** `laion/larger_clap_music` does not reliably distinguish metal subgenres (gothic, doom, black, death) — it tends toward generic labels like "r&b" or "electronic". Adding specific subgenre tags to `DEFAULT_TAG_SETS` helps marginally. For production use, a fine-tuned classifier is preferable.

**BPM octave errors:** The autocorrelation-based BPM estimator can return 2× the true tempo for slow/doom genres (e.g., 105 BPM reported as 154 BPM). No automatic correction implemented yet.

## Export Formats

| Format | Purpose |
|--------|---------|
| JSON | Default, re-importable, same schema as auto-save |
| CSV | Tabular, Excel-compatible |
| MD | Formatted report with table + medals |
| TXT | Plain-text terminal-style output |

## Roadmap

**Outstanding (near-term):**
- Create `resources/spotilyzer.ico` (app icon, currently missing)
- Improve Flop recall — add more Flop training samples
- GUI integration for CLAP: Settings checkbox (PRO mode) + CLAPResult display in ResultCard
- Expand CLAP `DEFAULT_TAG_SETS` with metal subgenres and more mood granularity
- Fix BPM octave error (halve if > configurable threshold, e.g., 160 BPM for slow genres)

**Medium-term:**
- MERT-v1-330M upgrade: switch embedder to `m-a-p/MERT-v1-330M` (1024-dim), retrain XGBoost in SpotilyzerTraining (overnight GPU job), swap `.joblib` — expected quality gain on ambiguous tracks
- "Sounds like..." — similarity search in embedding space
- Genre classification — second model for cluster assignment
- In-app genre cluster editor + scouting trigger (PRO mode)
- Model comparison panel (PRO mode)
- HF token support (`HF_TOKEN` env var) for higher rate limits

**Long-term:**
- Genre-specific models (one per cluster)
- Portable Windows EXE (PyInstaller + CUDA strip, targeting ~3 GB)
