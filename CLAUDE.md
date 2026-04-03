# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Spotilyzer (v2.0) is an ML-based audio analysis tool that classifies tracks as **Hit / Mid / Flop** based on mainstream compatibility. Pipeline: audio file → MERT-v1-95M embeddings (768-dim) → XGBoost 3-class classifier → GUI or CLI output.

The PySide6 GUI rewrite (from Tkinter) was designed around three pillars:
- **Three view modes**: Simple (drop zone only) / Balanced (default) / Pro (all dock panels)
- **Three UX tiers** (AppMode): same modes, control visibility of fields and features throughout
- **13 analysis fields per track**: rating, confidence, probabilities + 10 technical fields (BPM, LUFS, key, format, sample rate, bitrate, channels, duration, file size, energy)

### Dual-Goal Architecture

**Ziel 1 (Priorität):** Neutral-informationsorientierte Song-Analyse. Technische und musikalische Daten zur Reproduzierbarkeit eines Sounds, Stärken/Schwächen-Analyse.

**Ziel 2:** Hit-Potential-Bewertung als Entscheidungshilfe für Release-Priorisierung und Plattform-Performance-Einschätzung (TikTok etc.).

Bei Unklarheit: Ziel 1 hat Vorrang.

Optional CLAP layer (zero-shot, per-request): genre + mood tags via `laion/larger_clap_music`.

---

## Repository-Informationen

| | Dieses Projekt | Training-Subprojekt |
|---|----------------|---------------------|
| **Zweck** | GUI, CLI, Analyse-Pipeline | Datenakquise, Labeling, Modell-Training |
| **Lokal** | `G:\Dev\source\Spotilyzer` | `G:\Dev\source\SpotilyzerTraining` |
| **GitHub** | `github.com/AndreasV77/Spotilyzer` | `github.com/AndreasV77/SpotilyzerTraining` |

---

## WICHTIG: Training-Subprojekt

**Das Modell-Training wurde in ein separates Repository ausgelagert.**

### Was gehört wohin?

| Aufgabe | Repository |
|---------|------------|
| GUI, CLI, Analyse-Pipeline | **Spotilyzer** (hier) |
| Deezer-Scouting, Preview-Download | **SpotilyzerTraining** |
| Last.fm-Enrichment | **SpotilyzerTraining** |
| Label-Berechnung, Sample-Gewichtung | **SpotilyzerTraining** |
| XGBoost-Training | **SpotilyzerTraining** |
| MERT-Embedding-Extraktion | **SpotilyzerTraining** |
| Fertiges Modell (.joblib) | Wird von Training → Spotilyzer kopiert |

### Interface zwischen den Projekten

**Input (Training → Spotilyzer):**
- `models/spotilyzer_model.joblib` — trainiertes XGBoost-Modell
- `models/training_report.json` — Trainings-Metadaten (optional)

**Das Hauptprojekt hat KEINE Abhängigkeit zum Training-Repo.** Es konsumiert nur das fertige Modell.

### Bei Training-bezogenen Fragen

→ Siehe `G:\Dev\source\SpotilyzerTraining\CLAUDE.md`

**NICHT in diesem Repo:**
- Datenquellen ändern/erweitern
- Label-Strategie anpassen
- Neue Genre-Cluster definieren
- Modell-Architektur ändern

---

## Setup

- **Python**: 3.12 (dev env); minimum 3.10 per `pyproject.toml`; venv at `.venv-spotilyzer/` (5.7 GB inkl. CUDA-Libs)
- **Activate**: `.\.venv-spotilyzer\Scripts\Activate.ps1` (PowerShell)
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
legacy/                  # archived old Spotify-API-based scripts (read-only reference)
resources/               # GUI assets (icons, images)
models/                  # spotilyzer_model.joblib + training_report.json (bundled in exe)
# Root-level legacy files (NOT part of the package, kept for reference):
analyze_track.py         # legacy standalone CLI (predates spotilyzer.cli package)
spotilyzer_gui.py        # legacy Tkinter GUI (predates PySide6 rewrite)
```

### Legacy-Ordner `training/` (DEPRECATED)

Der `training/`-Ordner in diesem Repository ist **veraltet**. Die aktiven Training-Skripte befinden sich in:

```
G:\Dev\source\SpotilyzerTraining\
```

Die alten Skripte bleiben als Referenz erhalten, sollten aber nicht mehr verwendet werden.

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

Alle Metriken auf echtem Holdout-Set (20%, 4545 Samples). Quelle: SpotilyzerTraining `evaluation_report_*.json`.

### Aktives Modell: MERTv1330M_main+spotify_charts+kworb_validated_20260319 (1024-dim)

Trainiert auf **~22.722 validated Samples** (Deezer-Scouting + Spotify Top 200 Charts + Kworb historische Charts, 12 Märkte). ~14.991 Hits. XGBoost: max_depth=4, colsample=0.6, n_estimators=500.

| Metric | Value | Ziel |
|--------|-------|------|
| Balanced Accuracy | **64.2%** | ≥ 65% |
| Hit Recall | **86.9%** ✓ | ≥ 80% |
| Flop Recall | **67.5%** ✓ | ≥ 50% |
| Mid Recall | 34.7% | — |

**Training-Ceiling erreicht (Session 8, 2026-03-31):** Hyperparameter-Sweeps (max_depth 4→6, colsample 0.6→0.8) zeigen monotonen Trade-off: mehr Tiefe → Hit Recall ↑, BA/Flop ↓. Optimum bei depth=4, col=0.6. Post-hoc Logit-Adjustment (τ=0.25) erreicht BA=65.3% aber Hit Recall sinkt auf 73.2% — beide Ziele gleichzeitig technisch nicht erreichbar. Audio-only Decke bei ~64–65% BA. Nächste BA-Verbesserung erfordert zusätzliche Features (librosa, Metadaten) oder Artist-Dedup im Training.

### Vorgänger: MERTv1330M_main+spotify_charts+kworb_validated_20260319 (Session 5, ~8.960 val.)

| Metric | Value |
|--------|-------|
| Balanced Accuracy | 63.0% |
| Hit Recall | 72.8% |
| Flop Recall | 68.7% ✓ |

**Praktische Verwendung:** Hit Recall-Ziel ≥80% erreicht. Flop-Filter funktioniert gut. Mid-Klasse bleibt schwierig (34.7% Recall) — wird häufig mit Hit verwechselt.

**Model bias:** 85%+ Confidence = echtes Potential. < 60% = unsicher, als Mid behandeln. Deezer rank thresholds: Flop < 300k, Mid 300k–700k, Hit > 700k.

**Inference speed:** ~0.53s/Track (95M) / ~0.8s/Track (330M) auf GTX 1660 Ti.

**Modell-Vergleich:** Siehe `models/MODEL_COMPARISON.md`.

**Zur Verbesserung:** Training-Hyperparameter-Raum ausgeschöpft. BA-Steigerung über 65% erfordert Artist-level Dedup im Training (GroupKFold), librosa-Features, oder LightGBM-Vergleich. → SpotilyzerTraining.

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
|--------|---------|
| JSON | Default, re-importable, same schema as auto-save |
| CSV | Tabular, Excel-compatible |
| MD | Formatted report with table + medals |
| TXT | Plain-text terminal-style output |

---

## NEXT TASK: LAION CLAP Integration

### Ziel

Zero-Shot Genre/Mood-Klassifikation als neues Analyse-Feature. CLAP (Contrastive Language-Audio Pretraining) ermöglicht Text-Audio-Alignment: beliebige Tags gegen Audio prüfen, ohne Training.

### Modell

`laion/larger_clap_music` auf HuggingFace
- Musik-spezialisiert (528K Downloads)
- Native `transformers`-Integration
- ~600 MB VRAM
- Apache 2.0 Lizenz

### Implementierung

**Neues Modul:** `spotilyzer/core/clap_analyzer.py`

```python
# Singleton-Pattern wie MERTEmbedder
class CLAPAnalyzer:
    _instance = None
    
    @classmethod
    def get_instance(cls, device: str = "cuda") -> "CLAPAnalyzer":
        ...
    
    def analyze(self, audio_path: Path, tag_sets: dict[str, list[str]]) -> CLAPResult:
        """
        Args:
            audio_path: Pfad zur Audio-Datei
            tag_sets: {"genre": ["metal", "pop", ...], "mood": ["aggressive", "melancholic", ...]}
        
        Returns:
            CLAPResult mit Similarity-Scores pro Tag-Set
        """
        ...
```

**Neues Datenmodell:** `spotilyzer/data/models.py`

```python
@dataclass
class CLAPResult:
    genre_scores: dict[str, float]    # {"metal": 0.72, "pop": 0.18, ...}
    mood_scores: dict[str, float]     # {"aggressive": 0.65, "melancholic": 0.12, ...}
    top_tags: list[str]               # Top-5 über alle Sets
    
    def to_dict(self) -> dict: ...
    
    @classmethod
    def from_dict(cls, data: dict) -> "CLAPResult": ...
```

### Hardware-Policy (WICHTIG)

Aktuelle Hardware: GTX 1660 Ti (6 GB VRAM)
Geplant: Upgrade auf 16+ GB

**Architektur-Regeln:**
1. Lazy-Loading für CLAP-Modell (nicht beim Start laden)
2. Sequentielles Laden möglich: MERT entladen → CLAP laden → analysieren → CLAP entladen → MERT laden
3. Config-Parameter: `vram_mode: "parallel" | "sequential"`
4. Mit 16 GB später: beide Modelle parallel im VRAM

**KEINE Architektur-Entscheidungen auf Basis der 6 GB-Limitierung treffen.**

### Akzeptanzkriterien

- [x] `CLAPAnalyzer` Singleton mit lazy-loading
- [x] `CLAPResult` Dataclass mit Serialisierung
- [x] Konfigurierbare Tag-Sets (nicht hardcoded)
- [x] Integration in CLI: `--include-clap` Flag
- [x] Integration in GUI: Settings-Checkbox + Anzeige in Result-Card (PRO-Mode)
- [x] Sequentieller VRAM-Modus funktioniert auf 6 GB
- [ ] Tests für Similarity-Berechnung

### Referenz-Dokumente

- `!BU/Spotilyzer_Feature_Matrix.md` — Übersicht aller geplanten Features
- `!BU/Spotilyzer_GenAI_Encoder_Analysis.md` — Detailanalyse CLAP vs. HeartCLAP vs. ACE-Step

---

## Roadmap

**Outstanding (near-term):**
- ~~**CLAP GUI-Integration**~~ ✅ — Settings-Checkbox (PRO mode) + CLAPResult in ResultCard implementiert
- ~~**librosa BPM-Fix**~~ ✅ — librosa Dynamic-Programming Beat Tracker + Oktavkorrektur (Session 9, 2026-04-01)
- ~~**librosa Energy-Ersatz**~~ ✅ — Spectral Centroid (Hz), Flatness (0-1), Onset Rate (/s) in AudioInfo (Session 9)
- ~~**`spotilyzer/analysis/` Phase-1-Modul**~~ ✅ — spectral, temporal, production features + FeatureExtractor + to_ki_context() (Session 9)
- ~~**Key-Erkennung**~~ ✅ — chroma_cqt + chroma_cens (librosa) statt manuelles STFT-Loop (Session 9)
- ~~**`spotilyzer/analysis/` Phase-2-Modul**~~ ✅ — DiagnosticResult (7-Band Mix-Analyse) + RoleResult (HPSS Instrument-Rollen) (Session 10, 2026-04-02)
- ~~**CLI `--full-analysis` / `--no-rating`**~~ ✅ — Spektral-Analyse in CLI integriert (Session 10)
- ~~**CLI `--threesome` Batch-Modus**~~ ✅ — BPM/LUFS/TruePeak/PLR/Key als Tabelle, Ordner+Glob-Support (Session 10)
- ~~**True Peak EBU R128**~~ ✅ — 4× Oversampling via scipy.signal.resample_poly, erkennt Inter-Sample-Clipping (Session 10)
- ~~95M-Neutraining~~ ✅ — MERTv195M_20260317 trainiert (BA=47.8%, Hit=5.6% — schlechter als 330M, noch nicht deployed)

**Medium-term:**
- **Essentia-Integration** — Stub `analysis/essentia_features.py` vorhanden (key+danceability+rhythm). Kein PyPI-Wheel für Windows; benötigt MSVC + CMake + Eigen3 + libav via vcpkg zum Kompilieren. WSL/Conda ausgeschlossen. Revisit wenn nativer Windows-Build stabil. **Nicht in portable EXE bundeln** (native C++-Deps, PyInstaller-inkompatibel).
- ~~MERT-v1-330M upgrade~~ ✅ — done: embedder switched to `m-a-p/MERT-v1-330M` (1024-dim), XGBoost retrained; Hit Recall ≥80% erreicht (86.9%, Session 6)
- ~~Mehr Hit-Samples via Kworb-Scraper + Spotify Charts~~ ✅ — 22.722 Samples, Hit Recall 86.9% (SpotilyzerTraining Sessions 5–6)
- "Sounds like..." — similarity search in embedding space
- Genre classification — second model for cluster assignment
- In-app genre cluster editor + scouting trigger (PRO mode)
- Model comparison panel (PRO mode)
- ~~HF token support (`HF_TOKEN` env var)~~ ✅ — set as Windows user env var
- ACE-Step Auto-Labeling (BPM/Key/TimeSignature validation)
- HeartCLAP evaluation (if LAION CLAP insufficient for music)

**Long-term:**
- Genre-specific models (one per cluster)
- Portable Windows EXE (PyInstaller + CUDA strip, targeting ~3 GB)
- Stem-basierte Analyse (Demucs/MDX-Net Integration)
- BA ≥65% via GroupKFold-Training (Artist-Dedup) oder zusätzliche Features (SpotilyzerTraining)

---

## Bekannte Audio-Metriken-Probleme (v2.0)

| Metrik | Problem | Fix |
|--------|---------|-----|
| ~~**LUFS**~~ | ~~RMS-Approximation, nicht EBU R128~~ | ✅ `pyloudnorm` integriert (EBU R128 K-weighting) |
| ~~**BPM**~~ | ~~Tempo-Verdopplung/-Halbierung~~ | ✅ librosa DP Beat Tracker + Oktavkorrektur (Session 9) |
| ~~**Energy**~~ | ~~Willkürliche Skalierung, unklare Definition~~ | ✅ Spectral Centroid, Flatness, Onset Rate (Session 9) |
| ~~**True Peak**~~ | ~~Sample-Maximum erkennt kein Inter-Sample-Clipping~~ | ✅ 4× Oversampling EBU R128 via scipy (Session 10) |
| **BPM Metrik-Ebene** | Beat Tracker trifft Quarter-Note-Puls, nicht immer die wahrgenommene Ebene (Half-Time/Double-Time-Feel) | Offen — erfordert genre-spezifische Heuristik |
