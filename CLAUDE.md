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

- **Python**: 3.12 (dev env); minimum 3.10 per `pyproject.toml`; venv at `.venv312/`
- **Activate**: `.\.venv312\Scripts\Activate.ps1` (PowerShell)
- **Install core**: `pip install -e .`
- **Install with dev deps**: `pip install -e ".[dev]"` (adds pyinstaller, pytest)
- **Model required**: `models/spotilyzer_model.joblib` must exist before running
- **MERT model** (~380 MB): auto-downloaded by HuggingFace `transformers` on first run to `~/.cache/huggingface/hub/`

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
# Or, after pip install:
spotilyzer-cli "track.mp3" --style json

# Build standalone Windows EXE
pyinstaller spotilyzer.spec
# After build, strip unnecessary CUDA libs (~1.5 GB savings):
python strip_cuda.py
```

## Package Architecture

```
spotilyzer/              # installable package (pyproject.toml), version 2.0.0
  __init__.py            # SUPPORTED_FORMATS, MERT_MODEL_NAME="m-a-p/MERT-v1-95M",
                         # TARGET_SAMPLE_RATE=24000, MAX_AUDIO_LENGTH_SEC=30
  core/
    pipeline.py          # AnalysisPipeline — orchestrates Embedder + Predictor + AudioInfo
    embedder.py          # MERTEmbedder (singleton) — loads MERT, extracts 768-dim embeddings
    predictor.py         # SpotilyzerPredictor — wraps XGBoost model (.joblib dict)
    audio_info.py        # extract_audio_info(), extract_waveform_display()
  cli/
    analyze.py           # CLI entry; uses AnalysisPipeline, --style default|minimal|json
  gui/
    app.py               # SpotilyzerApp (QMainWindow) — central coordinator, all wiring
    central.py           # CentralWidget — DropZone + result list + stats bar
    worker.py            # QThread workers: PipelineInitWorker, AnalysisWorker, WaveformWorker
    theme.py             # ThemeManager — generates QSS for Dark/Light + accent color
    panels/              # QDockWidgets: file_panel, highscore_panel, history_panel,
                         #               tech_panel (waveform + audio preview), settings_panel
    widgets/             # dropzone.py, result_card.py, confidence_bar.py, waveform.py
  data/
    models.py            # AnalysisResult, AudioInfo, ModelInfo, Rating/AppMode/SortMode enums
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

**Model file format**: `models/spotilyzer_model.joblib` is a `dict` with keys `"model"` (XGBoost) and `"label_encoder"` (sklearn LabelEncoder). The optional `models/training_report.json` provides metadata shown in the GUI.

**Audio preprocessing**: mono conversion → resample to 24 kHz → clip to center 30 seconds before embedding.

**GUI threading**: all ML work runs in QThread workers (`worker.py`). Pipeline initializes 100ms after startup via `QTimer.singleShot`. Never call pipeline methods from the main thread.

**Three-tier UX (AppMode)**: all 13 analysis fields are always computed — the tier only controls visibility. `SIMPLE` hides all dock panels; `BALANCED` shows highscore, history, tech panels; `PRO` shows all panels including file browser and settings.

**Result card grid-snap**: Implemented. `ResultCard` uses `CARD_HEIGHTS = {SIMPLE: 68, BALANCED: 88, PRO: 88}` with `setFixedHeight()`. `CentralWidget.resizeEvent` calls `_adjust_results_viewport()` to snap the visible area to a multiple of card height. Scroll step is set to card height. DropZone collapses to 50 px (compact mode) when results are present.

**Auto-save**: results persist to `spotilyzer_results.json` in CWD after each batch. Loaded automatically on startup. Format version `"2.0"`.

**Model search order** (GUI): `models/spotilyzer_model.joblib` → project root → `~/.spotilyzer/models/` → PyInstaller bundle (`sys._MEIPASS`).

**Audio preview**: `QMediaPlayer` + `QAudioOutput` from `PySide6.QtMultimedia`. Supports MP3, FLAC, WAV, OGG via Windows Media Foundation backend.

**Layout persistence**: dock panel positions saved/restored via `QSettings.saveState()` / `restoreState()`. Organization: `"Spotilyzer"`, App: `"Spotilyzer"`.

**Packaging**: PyInstaller `--onedir` via `spotilyzer.spec`. MERT (~380 MB) is NOT bundled — downloaded on first run. After build, `strip_cuda.py` removes unused CUDA DLLs (cuFFT, cuSolver, cuSparse, cuRand, cuPTI, all `.lib` files) saving ~1.5 GB. Total bundled size ~3 GB.

## Supported Audio Formats

`.mp3`, `.flac`, `.wav`, `.ogg`, `.m4a`, `.aac`, `.wma`

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

**Model bias:** Defaults to "Hit" under uncertainty. Practical interpretation: 85%+ confidence = genuine potential; below 60% = treat as uncertain.

**Inference speed:** ~0.53s/track on GTX 1660 Ti.

**Zur Verbesserung dieser Metriken:** Siehe SpotilyzerTraining-Subprojekt.

## Known Issues & Gotchas

**App icon missing:** `resources/spotilyzer.ico` does not exist yet. The `spotilyzer.spec` conditionally includes it if present — the build works without it, but the window and taskbar will show the default Qt icon.

**Drag & Drop + admin shell (Windows UIPI):** D&D from Explorer does not work when the app runs in an elevated terminal. Run `python main.py` from a non-admin shell, or use the file-open dialog instead.

**PySide6 enum/string coercion:** `QComboBox.currentData()` and `QSettings.value()` return plain strings, not Python enum instances. The codebase guards against this (e.g., `AppMode(str(mode))` in `app.py`, `settings_panel.py`). Don't assume signal payloads are always enum instances when adding new signal connections.

**MERT first-run download:** ~380 MB, requires internet, cached at `~/.cache/huggingface/hub/models--m-a-p--MERT-v1-95M/`.

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

- [ ] `CLAPAnalyzer` Singleton mit lazy-loading
- [ ] `CLAPResult` Dataclass mit Serialisierung
- [ ] Konfigurierbare Tag-Sets (nicht hardcoded)
- [ ] Integration in CLI: `--include-clap` Flag
- [ ] Integration in GUI: Settings-Checkbox + Anzeige in Result-Card (PRO-Mode)
- [ ] Sequentieller VRAM-Modus funktioniert auf 6 GB
- [ ] Tests für Similarity-Berechnung

### Referenz-Dokumente

- `!BU/Spotilyzer_Feature_Matrix.md` — Übersicht aller geplanten Features
- `!BU/Spotilyzer_GenAI_Encoder_Analysis.md` — Detailanalyse CLAP vs. HeartCLAP vs. ACE-Step

---

## Roadmap

**Outstanding (near-term):**
- Create `resources/spotilyzer.ico` (app icon, currently missing)
- **LAION CLAP Integration** (see NEXT TASK above)

**Medium-term:**
- "Sounds like..." — similarity search in embedding space
- Genre classification — second model for cluster assignment
- In-app genre cluster editor + scouting trigger (PRO mode)
- Model comparison panel (PRO mode)
- ACE-Step Auto-Labeling (BPM/Key/TimeSignature validation)
- HeartCLAP evaluation (if LAION CLAP insufficient for music)

**Long-term:**
- Genre-specific models (one per cluster)
- Portable Windows EXE (PyInstaller + CUDA strip, targeting ~3 GB)
- Stem-basierte Analyse (Demucs/MDX-Net Integration)

---

## Bekannte Audio-Metriken-Probleme (v2.0)

| Metrik | Problem | Fix |
|--------|---------|-----|
| **LUFS** | RMS-Approximation, nicht EBU R128 | `pyloudnorm` Bibliothek |
| **BPM** | Tempo-Verdopplung/-Halbierung | `librosa.beat.tempo()` |
| **Energy** | Willkürliche Skalierung, unklare Definition | Aufteilen in Spectral Centroid, Flatness, Onset Rate |

Diese Fixes sind Quick-Wins (je ~2-4h) und können parallel zur CLAP-Integration erfolgen.
