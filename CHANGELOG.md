# Changelog

Format: `YYYY-MM-DD — <file(s)> — <what changed>` · newest on top.
Code changes reference the short commit hash where available.
Append-only: never rewrite or delete past entries. One change = one line.
History before the first entry below lives in `git log`.

---

## 2026-06-02
- spotilyzer/gui/app.py — duplicate guard in _on_result_ready: path-based check skips result if same path already in _results (prevents double-analysis of folders with symlinked/copied files).
- spotilyzer/gui/app.py — settings persistence fix: QApplication.aboutToQuit connected to _save_app_settings as fallback for Ctrl+C terminal kills (closeEvent not triggered).
- spotilyzer/gui/app.py — settings persistence fix: restoreGeometry/restoreState moved out of _load_app_settings into new _restore_window_state(); deferred via QTimer.singleShot(0) to run after show(), prevents Qt overwriting geometry on first paint.

## 2026-05-31
- spotilyzer/core/similarity.py — new: cosine_similarity() + find_similar(); session-only, compares mean-pooled MERT embeddings.
- spotilyzer/data/models.py — AnalysisResult: added _embedding field (non-persistent, session-only, like _waveform).
- spotilyzer/core/pipeline.py — stores mean-pooled track embedding in result._embedding after prediction.
- spotilyzer/gui/panels/tech_panel.py — "Klingt ähnlich wie" section: set_similar() renders top-N similar tracks with rating colour + similarity %.
- spotilyzer/gui/app.py — _on_result_clicked calls find_similar() and passes results to TechPanel.

## 2026-05-30 (continued)
- tests/test_clap.py, tests/conftest.py — CLAP test suite: 20 unit tests covering CLAPResult serialization, audio resampling, waveform chunking, score aggregation and top-tag ranking; model mocked (no weights download); @pytest.mark.slow integration test for real inference.
- pyproject.toml — pytest slow marker registered.
- spotilyzer/gui/widgets/waveform.py — waveform rendering fix: paintEvent now iterates over widget pixels (x=0…w-1) and maps to data via idx=int(x*n/w); previously x=int(i*x_scale) compressed all bars into ~38% of widget width when target_width > widget width.
- spotilyzer/core/clap_analyzer.py — CLAP fix: resample audio to 48 kHz before ClapFeatureExtractor (raises ValueError instead of resampling silently); prior 44.1 kHz files produced no result.
- spotilyzer/core/pipeline.py — CLAP error isolation: CLAP block now has its own try/except; ValueError/RuntimeError from CLAP no longer discards the already-computed MERT rating.
- spotilyzer/core/pipeline.py — SP-011: _build_model_info now uses _find_report_path() to glob training_report_*.json (date-matched or newest); bare-name fallback removed; model metadata now visible in GUI.

## 2026-05-30
- CLAUDE.md — added Documentation Workflow pointer (audit/errata/fix cycle)
- CLAUDE.md — SP-002: Predecessor block replaced with correct Alternative model entry (_20260319 = depth=4 BA-optimal, 22,722 val., BA 64.2 / Hit 82.5 / Flop 73.5); removed erroneous Session-5 metrics.
- README.md — SP-001: Balanced Accuracy corrected from 64.2% to 63.0% (default _20260529); phantom metric combination eliminated.
- CLAUDE.md — SP-004: Active model block now explains depth=5 chosen for higher Hit Recall; depth=4 is BA-optimal Alternative.
- models/MODEL_COMPARISON.md — SP-007: Removed "(Noch zu implementieren)" note; inference architecture marked implemented (commit aebb131); task #1 removed from Open Tasks.
- models/MODEL_COMPARISON.md — SP-008: Full DE→EN translation per Translation Policy.
- CLAUDE.md — SP-003: Added active_model.txt to model search order (between QSettings path and mtime glob).
- CLAUDE.md, README.md — SP-005: Added note that holdout metrics are per 30s clip; song-level evaluation still pending.
- CLAUDE.md, README.md — SP-006: Setup instruction updated: active mechanism is spotilyzer_model_*.joblib + active_model.txt; bare spotilyzer_model.joblib is legacy fallback only.
- README.md — SP-009: training/ folder marked DEPRECATED in Package Structure; active scripts are in SpotilyzerTraining repo.
- CLAUDE.md — SP-010: Interface section and Model file format updated to full-named training_report_*.json pattern; code gap in pipeline.py documented (bare-name lookup → empty metadata); SP-011 logged as new OPEN defect.

## 2026-05-29
- predictor.py / embedder.py / pipeline.py — chunk-averaging inference: each 30s chunk scored independently, probabilities averaged (no embedding mean-pool). Commit `aebb131`.
- models/active_model.txt — added; CLI (`_find_default_model`) and GUI (`_find_model_path`) now read it ahead of the mtime glob. Resolves the silent "newest-by-mtime" default.
- models/ — `_20260529` deployed as default; `_20260331` archived.
- CLAUDE.md — active model set to `_20260529`; chunk-averaging documented in audio-preprocessing section.

## (earlier)
- See `git log`. English-translation pass and pre-2026-05-29 history not retro-logged.
