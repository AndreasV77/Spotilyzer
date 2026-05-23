# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Spotilyzer (v2.0) is an ML-based audio analysis tool that classifies tracks as **Hit / Mid / Flop** based on mainstream compatibility. Pipeline: audio file → MERT-v1-95M embeddings (768-dim) → XGBoost 3-class classifier → GUI or CLI output.

The PySide6 GUI rewrite (from Tkinter) was designed around three pillars:
- **Three view modes**: Simple (drop zone only) / Balanced (default) / Pro (all dock panels)
- **Three UX tiers** (AppMode): same modes, control visibility of fields and features throughout
- **13 analysis fields per track**: rating, confidence, probabilities + 10 technical fields (BPM, LUFS, key, format, sample rate, bitrate, channels, duration, file size, energy)

### Dual-Goal Architecture

**Goal 1 (Priority):** Neutral, information-oriented song analysis. Technical and musical data for reproducing a sound and identifying strengths/weaknesses.

**Goal 2:** Hit-potential assessment as decision support for release prioritization and platform performance estimation (TikTok etc.).

When in doubt: Goal 1 takes priority.

Optional CLAP layer (zero-shot, per-request): genre + mood tags via `laion/larger_clap_music`.

---

## Repository Information

| | This Project | Training Sub-project |
|---|----------------|---------------------|
| **Purpose** | GUI, CLI, analysis pipeline | Data acquisition, labeling, model training |
| **Local** | `G:\Dev\source\Spotilyzer` | `G:\Dev\source\SpotilyzerTraining` |
| **GitHub** | `github.com/AndreasV77/Spotilyzer` | `github.com/AndreasV77/SpotilyzerTraining` |

---

## IMPORTANT: Training Sub-project

**Model training has been moved to a separate repository.**

### What Goes Where?

| Task | Repository |
|---------|------------|
| GUI, CLI, analysis pipeline | **Spotilyzer** (here) |
| Deezer scouting, preview download | **SpotilyzerTraining** |
| Last.fm enrichment | **SpotilyzerTraining** |
| Label calculation, sample weighting | **SpotilyzerTraining** |
| XGBoost training | **SpotilyzerTraining** |
| MERT embedding extraction | **SpotilyzerTraining** |
| Finished model (.joblib) | Copied from Training → Spotilyzer |

### Interface Between Projects

**Input (Training → Spotilyzer):**
- `models/spotilyzer_model.joblib` — trained XGBoost model
- `models/training_report.json` — training metadata (optional)

**The main project has NO dependency on the training repo.** It only consumes the finished model.

### For Training-Related Questions

→ See `G:\Dev\source\SpotilyzerTraining\CLAUDE.md`

**NOT in this repo:**
- Modify/extend data sources
- Adjust label strategy
- Define new genre clusters
- Change model architecture

---

## Setup

- **Python**: 3.12 (dev env); minimum 3.10 per `pyproject.toml`; venv at `.venv-spotilyzer/` (5.7 GB incl. CUDA libs)
- **Activate**: `.\venv-spotilyzer\Scripts\Activate.ps1` (PowerShell)
- **Install core**: `pip install -e .`
- **Install with dev deps**: `pip install -e ".[dev]"` (adds pyinstaller, pytest)
- **Model required**: `models/spotilyzer_model.joblib` must exist before running
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

# Build standalone Windows EXE
pyinstaller spotilyzer.spec
# After build, strip unnecessary CUDA libs (~1.5 GB savings):
python strip_cuda.py
```

**⚠ Dev-Worktree caveat**: The editable install's package lookup is shadowed by the main repo's `spotilyzer/` directory if Python is invoked from `G:\Dev\Source\Spotilyzer\`. Always `cd` into the worktree before using `-m spotilyzer.cli.analyze`.

## Package Architecture

```
spotilyzer/              # installable package (pyproject.toml), version 2.0.0
  __init__.py            # SUPPORTED_FORMATS, MERT_MODEL_NAME="m-a-p/MERT-v1-330M",
                         # MERT_EMBEDDING_DIM=1024, CLAP_MODEL_NAME="laion/larger_clap_music",
                         # TARGET_SAMPLE_RATE=24000, MAX_AUDIO_LENGTH_SEC=30
  core/
    pipeline.py          # AnalysisPipeline — orchestrates Embedder + Predictor + AudioInfo + CLAP
    embedder.py          # MERTEmbedder (singleton) — loads MERT, extracts 1024-dim embeddings (330M) / 768-dim (95M)
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
  locale/
    __init__.py          # t() translation function, load() locale loader
    EN/
      __init__.py
      strings.py         # All English UI strings
legacy/                  # archived old Spotify-API-based scripts (read-only reference)
resources/               # GUI assets (icons, images)
models/                  # spotilyzer_model.joblib + training_report.json (bundled in exe)
# Root-level legacy files (NOT part of the package, kept for reference):
analyze_track.py         # legacy standalone CLI (predates spotilyzer.cli package)
spotilyzer_gui.py        # legacy Tkinter GUI (predates PySide6 rewrite)
```

### Legacy `training/` Folder (DEPRECATED)

The `training/` folder in this repository is **outdated**. The active training scripts are in:

```
G:\Dev\source\SpotilyzerTraining\
```

The old scripts are kept as reference but should no longer be used.

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

**Model search order** (GUI): Custom path in QSettings (highest priority) → glob `models/spotilyzer_model_*.joblib` (newest by mtime) → project root → `~/.spotilyzer/models/` → fallback to legacy `spotilyzer_model.joblib` → PyInstaller bundle (`sys._MEIPASS`).

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

All metrics on real holdout set (20%, 4545 samples). Source: SpotilyzerTraining `evaluation_report_*.json`.

### Active Model: MERTv1330M_main+spotify_charts+kworb_validated_20260319 (1024-dim)

Trained on **~22,722 validated samples** (Deezer scouting + Spotify Top 200 Charts + Kworb historical charts, 12 markets). ~14,991 Hits. XGBoost: max_depth=4, colsample=0.6, n_estimators=500.

| Metric | Value | Target |
|--------|-------|--------|
| Balanced Accuracy | **64.2%** | ≥ 65% |
| Hit Recall | **86.9%** ✓ | ≥ 80% |
| Flop Recall | **67.5%** ✓ | ≥ 50% |
| Mid Recall | 34.7% | — |

**Training ceiling reached (Session 8, 2026-03-31):** Hyperparameter sweeps (max_depth 4→6, colsample 0.6→0.8) show monotonic trade-off: more depth → Hit Recall ↑, BA/Flop ↓. Optimum at depth=4, col=0.6. Post-hoc logit adjustment (τ=0.25) achieves BA=65.3% but Hit Recall drops to 73.2% — both targets simultaneously not achievable technically. Audio-only ceiling at ~64–65% BA. Next BA improvement requires additional features (librosa, metadata) or artist dedup in training.

### Predecessor: MERTv1330M_main+spotify_charts+kworb_validated_20260319 (Session 5, ~8,960 val.)

| Metric | Value |
|--------|-------|
| Balanced Accuracy | 63.0% |
| Hit Recall | 72.8% |
| Flop Recall | 68.7% ✓ |

**Practical use:** Hit Recall target ≥80% reached. Flop filter works well. Mid class remains difficult (34.7% Recall) — frequently confused with Hit.

**Model bias:** 85%+ confidence = genuine potential. < 60% = uncertain, treat as Mid. Deezer rank thresholds: Flop < 300k, Mid 300k–700k, Hit > 700k.

**Inference speed:** ~0.53s/track (95M) / ~0.8s/track (330M) on GTX 1660 Ti.

**Model comparison:** See `models/MODEL_COMPARISON.md`.

**For improvement:** Training hyperparameter space exhausted. BA improvement beyond 65% requires artist-level dedup in training (GroupKFold), librosa features, or LightGBM comparison. → SpotilyzerTraining.

## Known Issues & Gotchas

**Drag & Drop + admin shell (Windows UIPI):** D&D from Explorer does not work when the app runs in an elevated terminal. Run `python main.py` from a non-admin shell, or use the file-open dialog instead.

**PySide6 enum/string coercion:** `QComboBox.currentData()` and `QSettings.value()` return plain strings, not Python enum instances. The codebase guards against this (e.g., `AppMode(str(mode))` in `app.py`, `settings_panel.py`). Don't assume signal payloads are always enum instances when adding new signal connections.

**MERT first-run download:** ~380 MB, requires internet, cached at `~/.cache/huggingface/hub/models--m-a-p--MERT-v1-95M/`.

**CLAP first-run download:** ~776 MB, cached at `~/.cache/huggingface/hub/models--laion--larger_clap_music/`.

**MERT loads on CPU despite CUDA being available:** Likely a `torch` CPU-only wheel in the venv. Verify with `python -c "import torch; print(torch.cuda.is_available())"`. Reinstall with CUDA-enabled torch if needed.

**CLAP genre accuracy on niche genres:** `laion/larger_clap_music` does not reliably distinguish metal subgenres (gothic, doom, black, death) — it tends toward generic labels like "r&b" or "electronic". Adding specific subgenre tags to `DEFAULT_TAG_SETS` helps marginally. For production use, a fine-tuned classifier is preferable.

**BPM metric-level ambiguity:** librosa's DP beat tracker detects the Quarter-Note pulse. In genres with strong Half-Time feel (e.g., AI-generated metal/electronic), the detected BPM may be the "groove pulse" rather than the "felt" tempo. Example: 4 AI-generated tracks measured at 92–117 BPM felt like 140–150 BPM. Root cause unclear without knowing the DAW project BPM. No automatic correction — genre-specific heuristic would be required.

## Export Formats

| Format | Purpose |
|--------|----------|
| JSON | Default, re-importable, same schema as auto-save |
| CSV | Tabular, Excel-compatible |
| MD | Formatted report with table + medals |
| TXT | Plain-text terminal-style output |

---

## NEXT TASK: LAION CLAP Integration

### Goal

Zero-shot genre/mood classification as a new analysis feature. CLAP (Contrastive Language-Audio Pretraining) enables text-audio alignment: check arbitrary tags against audio without training.

### Model

`laion/larger_clap_music` on HuggingFace
- Music-specialized (528K downloads)
- Native `transformers` integration
- ~600 MB VRAM
- Apache 2.0 license

### Implementation

**New module:** `spotilyzer/core/clap_analyzer.py`

```python
# Singleton pattern like MERTEmbedder
class CLAPAnalyzer:
    _instance = None
    
    @classmethod
    def get_instance(cls, device: str = "cuda") -> "CLAPAnalyzer":
        ...
    
    def analyze(self, audio_path: Path, tag_sets: dict[str, list[str]]) -> CLAPResult:
        """
        Args:
            audio_path: Path to the audio file
            tag_sets: {"genre": ["metal", "pop", ...], "mood": ["aggressive", "melancholic", ...]}
        
        Returns:
            CLAPResult with similarity scores per tag set
        """
        ...
```

**New data model:** `spotilyzer/data/models.py`

```python
@dataclass
class CLAPResult:
    genre_scores: dict[str, float]    # {"metal": 0.72, "pop": 0.18, ...}
    mood_scores: dict[str, float]     # {"aggressive": 0.65, "melancholic": 0.12, ...}
    top_tags: list[str]               # Top-5 across all sets
    
    def to_dict(self) -> dict: ...
    
    @classmethod
    def from_dict(cls, data: dict) -> "CLAPResult": ...
```

### Hardware Policy (IMPORTANT)

Current hardware: GTX 1660 Ti (6 GB VRAM)
Planned: Upgrade to 16+ GB

**Architecture rules:**
1. Lazy-loading for CLAP model (do not load at startup)
2. Sequential loading possible: offload MERT → load CLAP → analyze → offload CLAP → load MERT
3. Config parameter: `vram_mode: "parallel" | "sequential"`
4. With 16 GB later: both models in VRAM simultaneously

**DO NOT make architecture decisions based on the 6 GB limitation.**

### Acceptance Criteria

- [x] `CLAPAnalyzer` singleton with lazy-loading
- [x] `CLAPResult` dataclass with serialization
- [x] Configurable tag sets (not hardcoded)
- [x] CLI integration: `--include-clap` flag
- [x] GUI integration: settings checkbox + display in Result-Card (PRO mode)
- [x] Sequential VRAM mode works on 6 GB
- [ ] Tests for similarity calculation

### Reference Documents

- `!BU/Spotilyzer_Feature_Matrix.md` — overview of all planned features
- `!BU/Spotilyzer_GenAI_Encoder_Analysis.md` — detailed analysis CLAP vs. HeartCLAP vs. ACE-Step

---

## Roadmap

**Outstanding (near-term):**
- ~~**CLAP GUI integration**~~ ✅ — Settings checkbox (PRO mode) + CLAPResult in ResultCard implemented
- ~~**librosa BPM fix**~~ ✅ — librosa Dynamic-Programming Beat Tracker + octave correction (Session 9, 2026-04-01)
- ~~**librosa Energy replacement**~~ ✅ — Spectral Centroid (Hz), Flatness (0-1), Onset Rate (/s) in AudioInfo (Session 9)
- ~~**`spotilyzer/analysis/` Phase-1 module**~~ ✅ — spectral, temporal, production features + FeatureExtractor + to_ki_context() (Session 9)
- ~~**Key detection**~~ ✅ — chroma_cqt + chroma_cens (librosa) instead of manual STFT loop (Session 9)
- ~~**`spotilyzer/analysis/` Phase-2 module**~~ ✅ — DiagnosticResult (7-band mix analysis) + RoleResult (HPSS instrument roles) (Session 10, 2026-04-02)
- ~~**CLI `--full-analysis` / `--no-rating`**~~ ✅ — spectral analysis integrated into CLI (Session 10)
- ~~**CLI `--threesome` batch mode**~~ ✅ — BPM/LUFS/TruePeak/PLR/Key as table, folder+glob support (Session 10)
- ~~**True Peak EBU R128**~~ ✅ — 4× oversampling via scipy.signal.resample_poly, detects inter-sample clipping (Session 10)
- ~~95M retraining~~ ✅ — MERTv195M_20260317 trained (BA=47.8%, Hit=5.6% — worse than 330M, not yet deployed)

**Medium-term:**
- **Essentia integration** — Stub `analysis/essentia_features.py` present (key+danceability+rhythm). No PyPI wheel for Windows; requires MSVC + CMake + Eigen3 + libav via vcpkg to compile. WSL/Conda excluded. Revisit when native Windows build is stable. **Do not bundle in portable EXE** (native C++ deps, PyInstaller-incompatible).
- ~~MERT-v1-330M upgrade~~ ✅ — done: embedder switched to `m-a-p/MERT-v1-330M` (1024-dim), XGBoost retrained; Hit Recall ≥80% reached (86.9%, Session 6)
- ~~More hit samples via Kworb scraper + Spotify Charts~~ ✅ — 22,722 samples, Hit Recall 86.9% (SpotilyzerTraining Sessions 5–6)
- "Sounds like..." — similarity search in embedding space
- Genre classification — second model for cluster assignment
- In-app genre cluster editor + scouting trigger (PRO mode)
- Model comparison panel (PRO mode)
- ~~HF token support (`HF_TOKEN` env var)~~ ✅ — set as Windows user env var
- ACE-Step auto-labeling (BPM/Key/TimeSignature validation)
- HeartCLAP evaluation (if LAION CLAP insufficient for music)

**Long-term:**
- Genre-specific models (one per cluster)
- Portable Windows EXE (PyInstaller + CUDA strip, targeting ~3 GB)
- Stem-based analysis (Demucs/MDX-Net integration)
- BA ≥65% via GroupKFold training (artist dedup) or additional features (SpotilyzerTraining)

---

## Known Audio Metrics Issues (v2.0)

| Metric | Issue | Fix |
|--------|-------|-----|
| ~~**LUFS**~~ | ~~RMS approximation, not EBU R128~~ | ✅ `pyloudnorm` integrated (EBU R128 K-weighting) |
| ~~**BPM**~~ | ~~Tempo doubling/halving~~ | ✅ librosa DP beat tracker + octave correction (Session 9) |
| ~~**Energy**~~ | ~~Arbitrary scaling, unclear definition~~ | ✅ Spectral Centroid, Flatness, Onset Rate (Session 9) |
| ~~**True Peak**~~ | ~~Sample maximum does not detect inter-sample clipping~~ | ✅ 4× oversampling EBU R128 via scipy (Session 10) |
| **BPM metric level** | Beat tracker hits quarter-note pulse, not always the perceived level (half-time/double-time feel) | Open — requires genre-specific heuristic |
