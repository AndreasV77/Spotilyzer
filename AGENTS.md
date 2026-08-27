# AGENTS.md — Spotilyzer

Project context for AI agents and AI reviewers other than Claude Code.

**This file is a point-in-time snapshot generated from `CLAUDE.md` (2026-07-14).**
`CLAUDE.md` is the sole authoritative document. If the two disagree, `CLAUDE.md` wins.
This snapshot is not continuously maintained.

## How to work with this document

- Architectural and strategic decisions recorded here are **settled**. If you see a
  problem, flag it with reasoning — do not re-plan the project or propose alternative
  architectures unprompted.
- All repository content (code, comments, docstrings, docs) is English-only.
- Documentation consistency uses a strict read-only **audit** → `ERRATA.md` → separate
  **fix pass** cycle (rules in `DOC_AUDIT.md`). Never mix auditing and fixing.
  Note: `ERRATA.md` and `DOC_AUDIT.md` are local-only working files and are not
  tracked in the public repository; only `CHANGELOG.md` is public.
- Metrics are always read from training/evaluation reports, never estimated.

---

## Project Overview

Spotilyzer (v2.0) is an ML-based audio analysis tool. Core pipeline:
audio file → MERT-v1-330M embeddings (1024-dim, per 30s chunk) → XGBoost 3-class
classifier (**Hit / Mid / Flop**, mainstream compatibility) → GUI or CLI output.

The PySide6 GUI (rewritten from Tkinter) is built around:
- **Three view modes / UX tiers** (Simple / Balanced / Pro) controlling panel and
  field visibility — all 13 analysis fields are always computed.
- **13 analysis fields per track**: rating, confidence, probabilities + 10 technical
  fields (BPM, LUFS, key, format, sample rate, bitrate, channels, duration, file
  size, energy metrics).
- Optional zero-shot **CLAP layer** (genre + mood tags, per request).

### Goals & Stage Model (authoritative since 2026-06-10)

Source: project goals document (`Spotilyzer_Ziele_und_Stufenmodell.md`). Note that
older passages — including parts of `CLAUDE.md` — still use a legacy "Goal 1 / Goal 2"
framing; the stage model below supersedes it.

**Product split:**

| Product | Purpose | Status |
|---------|---------|--------|
| **Quick-Spot** | Fast analysis: hit assessment + core technical data | Feature-complete; bugfixes and model updates only |
| **Spotilyzer** | Full music analysis per stage model | In development |
| **SpotilyzerTraining** | Model training; supplies models to both products | Ongoing |

Quick-Spot is a separate product but **not a code fork** — both products share the
same core library (inference pipeline, chunk averaging, model selection via
`active_model.txt`, BPM extraction). Model updates flow into both automatically.

**Stage model:**

- **Stage 1 — Numerical analysis** *(implemented, productive)*: MERT embeddings,
  Hit/Mid/Flop classification, technical metrics (BPM, key, duration, loudness).
- **Stage 2 — Fact layer ("what happens in the track")**: deterministically derived,
  verifiable statements in a format general LLMs can use as a reliable perceptual
  ground: song structure with timestamps, BPM/key/time signature with confidence,
  energy trajectory and section contrasts, frequency-band distribution, production
  metrics, instrument/vocal presence via CLAP tags (always with confidence values),
  chord-progression detection, annotated visual representations.
  *Acceptance criterion:* an LLM receiving only the Stage-2 package (no audio)
  answers factual questions correctly ("Where does the first chorus start?",
  "Male or female vocals?"), checked against ground truth of own tracks.
  *Design principle:* prefer "undetermined, low confidence" over guessing.
- **Stage 3 — Grounded description**: natural-language description of genre,
  composition, instrumentation, emotional effect — where **every claim must trace
  back to a Stage-2 feature or tag score** (grounded captioning: local caption
  models generate candidates, the Stage-2 fact layer validates/corrects, an LLM
  phrases the final description using only grounded statements).
  *Acceptance criterion:* measurably better than Suno upload captions and Tunee
  analyses on objectively verifiable items (vocal gender, genre assignment,
  present vs. hallucinated instruments, no confabulated chord progressions).

**Value proposition:** reliable, reproducible, fact-grounded music perception
instead of plausible guessing. Not a use case: mass batch processing —
single-track latency up to ~1 minute is acceptable.

---

## Repository Information

| | This Project | Training Sub-project |
|---|----------------|---------------------|
| **Purpose** | GUI, CLI, analysis pipeline | Data acquisition, labeling, model training |
| **Local** | `this repository` | `../SpotilyzerTraining` |
| **GitHub** | `github.com/AndreasV77/Spotilyzer` | `github.com/AndreasV77/SpotilyzerTraining` |

**Interface (Training → Spotilyzer):** the main project has **no dependency** on the
training repo. It only consumes finished artifacts:
- `models/spotilyzer_model_*.joblib` — trained XGBoost model (dict with keys
  `"model"` and `"label_encoder"`)
- `models/training_report_*.json` — training metadata (optional, shown in GUI)

Report resolution matches the active model's date tag (last `_`-segment of the model
stem) against `training_report_*{date}.json`, falling back to the newest report next
to the model, then to the bare legacy name.

**Not in this repo:** data sources, label strategy, genre clusters, model
architecture — all of that lives in SpotilyzerTraining.

---

## Setup & Commands

- **Python** 3.12 (dev env), minimum 3.10; venv at `.venv-spotilyzer/`
- Install: `pip install -e .` (dev: `pip install -e ".[dev]"`)
- At least one `models/spotilyzer_model_*.joblib` must exist. Active model selected
  via `models/active_model.txt`, else newest `.joblib` by mtime.
- MERT-v1-330M (~1.3 GB) and CLAP (~600 MB) auto-download via HuggingFace on
  first use.

```bash
python main.py                                   # GUI
python -m spotilyzer.cli.analyze "track.mp3"     # CLI, basic
python -m spotilyzer.cli.analyze "track.mp3" --style json --device cuda
python -m spotilyzer.cli.analyze "track.mp3" --include-clap --vram-mode sequential
pyinstaller spotilyzer.spec                      # standalone Windows EXE
python strip_cuda.py                             # post-build, ~1.5 GB savings
```

---

## Package Architecture

```
spotilyzer/
  __init__.py            # constants: MERT_MODEL_NAME, MERT_EMBEDDING_DIM=1024,
                         # CLAP_MODEL_NAME="laion/clap-htsat-fused",
                         # TARGET_SAMPLE_RATE=24000, MAX_AUDIO_LENGTH_SEC=30
  core/
    pipeline.py          # AnalysisPipeline — orchestrates Embedder + Predictor + AudioInfo + CLAP
    embedder.py          # MERTEmbedder (singleton), per-chunk embedding extraction
    predictor.py         # SpotilyzerPredictor — wraps XGBoost model
    audio_info.py        # technical metrics; LUFS via pyloudnorm (EBU R128)
    clap_analyzer.py     # CLAPAnalyzer (singleton) — zero-shot genre/mood
  cli/analyze.py         # CLI entry; --style, --include-clap, --vram-mode,
                         # --full-analysis, --no-rating, --threesome batch mode
  gui/                   # PySide6: app.py, central.py, QThread workers, theme,
                         # dock panels (file/highscore/history/tech/settings), widgets
  analysis/              # spectral/temporal/production features, diagnostics
                         # (7-band mix analysis), role features (HPSS),
                         # FeatureExtractor + to_ki_context(); essentia stub (blocked)
  data/                  # AnalysisResult/AudioInfo/CLAPResult models, persistence,
                         # export (JSON/CSV/MD/TXT)
  locale/EN/             # UI strings
models/                  # *.joblib + training_report_*.json + active_model.txt
legacy/, training/       # archived, read-only reference — do not use
```

---

## Key Design Decisions

- **MERTEmbedder and CLAPAnalyzer are singletons** (slow to load, stay in memory
  for the session).
- **Chunk-based inference:** mono → resample 24 kHz → 30s chunks (overlap-free,
  last chunk zero-padded, <5s tail discarded) → MERT embedding per chunk →
  XGBoost per chunk → **mean of probabilities** → final rating. Each chunk is
  scored independently, matching the training format (Deezer 30s previews =
  1 chunk = 1 embedding). Averaging happens on probability level, not embedding
  level — this resolves the earlier training/inference mismatch.
- **VRAM modes:** `vram_mode="sequential"` offloads MERT to CPU before CLAP loads
  and vice versa (for 6 GB GPUs); default `"concurrent"` keeps both on GPU.
- **Hardware policy:** design for the planned 16+ GB VRAM target; implement
  fallback modes for current hardware. **Never make architecture decisions based
  on the current VRAM limit.**
- **LUFS:** full EBU R128 via pyloudnorm; RMS fallback if unavailable.
  **True Peak:** 4× oversampling per EBU R128 (detects inter-sample clipping).
- **GUI threading:** all ML work in QThread workers; never call pipeline methods
  from the main thread.
- **torchaudio ≥ 2.5:** soundfile-first fallback pattern everywhere (torchcodec
  backend is not installed).
- **Packaging:** PyInstaller `--onedir`; MERT/CLAP not bundled (downloaded on
  first run); `strip_cuda.py` afterwards; total ~3 GB.

## Intended Usage Profile

Single-user Windows desktop app. Batch size typically 1–10 tracks per session.
Latency tolerance: a few seconds per track; single-track full analysis up to
~1 minute acceptable. **Quality over speed, correctness over throughput.**

---

## Model Performance (current)

Active model: `MERTv1330M_depth4refresh_main+spotify_charts+kworb_validated_20260713`
(SLYZR 1.3, 1024-dim). Trained on 24,170 validated samples (Deezer scouting +
Spotify Top 200 + Kworb historical charts, 12 markets). XGBoost depth=4/col=0.6 —
the standing hyperparameter default. Holdout: 4,834 samples (30s clips; song-level
evaluation still pending).

| Metric | Value | Target |
|--------|-------|--------|
| Balanced Accuracy | 64.3% | ≥ 65% |
| Hit Recall | 82.4% ✓ | ≥ 80% |
| Flop Recall | 74.5% ✓ | ≥ 50% |
| Mid Recall | 36.0% | — |

**Training ceiling reached:** hyperparameter sweeps show a monotonic trade-off
(more depth → Hit Recall ↑, BA/Flop ↓). Audio-only ceiling ~64–65% BA. Further BA
improvement requires artist dedup in training (GroupKFold), additional features,
or a different learner — all in SpotilyzerTraining.

**Interpretation guidance:** ≥85% confidence = genuine potential; <60% = uncertain,
treat as Mid. Mid class remains hard (frequently confused with Hit).

---

## Known Issues & Gotchas

- **CLAP checkpoint `laion/larger_clap_music` is broken on the HF Hub — do not
  use.** Its HF-converted text encoder collapses (`logit_scale_a.exp()` ≈ 1.0;
  arbitrary text embeddings 0.998+ cosine-similar), so tag scores are noise.
  Confirmed via LAION-AI/CLAP#126 and the HF discussion (reported Dec 2023,
  unfixed). The underlying original checkpoint
  (`music_audioset_epoch_15_esc_90.14.pt` via the `laion_clap` pip package) is
  fine — only the HF conversion is defective. Current model:
  `laion/clap-htsat-fused` (verified healthy).
- **CLAP genre accuracy on niche genres:** `clap-htsat-fused` is general-purpose —
  it does not reliably distinguish metal subgenres and shows an unexplained
  hip-hop bias. Recovering the music-specialized model via the original `.pt`
  checkpoint is planned, not implemented.
- **BPM metric-level ambiguity:** the DP beat tracker detects the quarter-note
  pulse; in genres with strong half-time feel the detected BPM may differ from
  the perceived tempo. No automatic correction (would need genre heuristics).
- **Drag & drop fails from Explorer into an elevated (admin) shell** (Windows UIPI).
- **PySide6 enum/string coercion:** `QComboBox.currentData()` and
  `QSettings.value()` return plain strings, not enum instances — guard accordingly.
- **Essentia:** no Windows PyPI wheel; native build required (MSVC/CMake/vcpkg).
  Stub module exists; revisit when a native build is stable. Never bundle in the
  portable EXE.

---

## Roadmap (condensed)

**Medium-term:** "Sounds like …" similarity search in embedding space; genre
classification (second model); in-app genre cluster editor + scouting trigger;
model comparison panel; ACE-Step auto-labeling (BPM/key/time-signature
validation); HeartCLAP evaluation (if LAION CLAP insufficient for music);
Essentia (blocked on Windows build).

**Long-term:** genre-specific models; portable Windows EXE (~3 GB); stem-based
analysis (Demucs/MDX-Net); BA ≥ 65% via GroupKFold or additional features
(→ SpotilyzerTraining).
