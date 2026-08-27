# Changelog

Format: `YYYY-MM-DD — <file(s)> — <what changed>` · newest on top.
Code changes reference the short commit hash where available.
Append-only: never rewrite or delete past entries. One change = one line.
History before the first entry below lives in `git log`.

---

## 2026-07-13
- CLAUDE.md — SP-012: "Practical use" Mid Recall corrected 34.7% → 36.0% (retired `_20260529` value replaced with the active `_20260713` report figure).
- CLAUDE.md — SP-013: "⚠ Known code gap" paragraph replaced with "Report resolution" describing the implemented date-tag match + glob fallback in `pipeline.py` (`_find_report_path()`); "Model file format" cross-reference updated. The gap was fixed 2026-05-30 (SP-011); the doc still described it as open.
- CLAUDE.md — SP-014: CLAP download size corrected ~776 MB → ~600 MB in Setup bullet and Packaging paragraph (measured local HF cache: 589 MB; Known Issues figure was already correct).
- CLAUDE.md, README.md — SP-015: package-tree `models/` comment updated from bare `spotilyzer_model.joblib + training_report.json` to actual contents (full-named `_*.joblib`/`_*.json`, `active_model.txt`, `model_names.json`).
- README.md — SP-016: "Model Performance (current)" updated to deployed `_20260713` (SLYZR 1.3): BA 64.3 / Hit 82.4 / Flop 74.5, 24,170 samples, 4,834 holdout (was retired `_20260529` figures).
- README.md — SP-017: Training section refreshed — dataset 24,170 validated samples / 15,980 hits (from `training_report_*_20260713.json`), Spotify Charts 10 markets (2026-07-13 CSV snapshot: au/br/de/fr/gb/global/jp/mx/se/us).
- README.md — SP-018: deployment Copy-Item glob for reports corrected `training_report_MERTv1330M_*_validated_*.json` → `training_report_MERTv1330M_*.json` (report filenames carry no `_validated_` segment; old glob matched nothing) + explanatory note.
- FEATURES.md — SP-019: hit-prediction metrics table and dataset/holdout counts updated to `_20260713` (64.3/82.4/74.5/36.0, 24,170 samples, 4,834 holdout); Known Limitations Mid recall 34.7% → 36.0%.
- CLAUDE.md — SP-020: CLAP acceptance criterion "Tests for similarity calculation" checked off (`tests/test_clap.py` exists, 22 test functions verified).
- DOC_AUDIT.md — added a "Repo hygiene" section to the audit pass (branch attachment, sync state, tracked-file/.gitignore gaps, working-tree cleanliness). Kept identical to SpotilyzerTraining's copy (canonical) — see that repo's CHANGELOG.md for the full rationale.
- models/ — deployed `spotilyzer_model_MERTv1330M_depth4refresh_main+spotify_charts+kworb_validated_20260713.joblib` (depth=4/col=0.6, SLYZR 1.3) as the new active model; `active_model.txt` updated. Retired `_20260529` (SLYZR 1.2, depth=5/col=0.8) to `<local-backup-archive>/Spotilyzer_model_20260529_retired_2026-07-13.zip` (its two report JSONs were git-tracked, removed via `git rm`). Verified via `spotilyzer.cli.analyze` end-to-end (model loads, model_id extracts correctly despite the `depth4refresh` filename segment, real inference runs) before committing.
- models/MODEL_COMPARISON.md, models/model_names.json — updated for the SpotilyzerTraining Session 11 hyperparameter sweep: depth=4/col=0.6 confirmed as standing default (depth=5/col=0.8, the retired model's config, judged a taste call not a technical win). Full comparison table and session history in MODEL_COMPARISON.md.
- models/ — removed `archive/` subfolder (7 old models/reports, some git-tracked) and the superseded `_20260319` Alternative model+reports; zipped to `<local-backup-archive>/Spotilyzer_model_archive_2026-07-13.zip` (shared zip with the SpotilyzerTraining-side cleanup, see that repo's changelog) before removal. Active `_20260529` (per `active_model.txt`) left untouched — removing it would leave the app without a working model until a replacement is explicitly chosen.
- spotilyzer/__init__.py — CLAP_MODEL_NAME switched from laion/larger_clap_music to laion/clap-htsat-fused: the former's HF conversion is defective (text encoder collapse, logit_scale_a≈1.0 vs healthy ~20-100; confirmed via LAION-AI/CLAP#126 and HF discussion #2), producing near-identical genre/mood scores regardless of audio content. General-purpose model accepted as interim trade-off; music-specialized recovery via laion_clap package planned (CLAP_Handoff_2026-07-13_v2.md).
- spotilyzer/data/models.py — AnalysisResult.model_id (str|None): date-suffix of the active model (e.g. "20260529"); serialized in to_dict()/from_dict(); None for legacy results (backward-compatible).
- spotilyzer/core/pipeline.py — model_id extracted from the model filename stem at init, exposed via new `model_id` property, set on every AnalysisResult produced.
- spotilyzer/data/persistence.py — new append_to_log()/load_log() for spotilyzer_log.jsonl: append-only historical record of all successful analyses, separate from the session cache spotilyzer_results.json; corrupt lines skipped on load.
- spotilyzer/gui/app.py — append_to_log() called on every successful result_ready.
- models/model_names.json — new: human-readable model aliases ("SLYZR 1.1"/"SLYZR 1.2") for future ModelPanel and result-card badges.
- spotilyzer/gui/panels/settings_panel.py — new set_current_mode(): syncs the mode ComboBox (and persisted view/mode key) when AppMode changes externally via toolbar buttons; fixes a desync where the Settings-panel dropdown showed a stale mode after restart even though the applied mode (app/mode key) was correctly restored.
- spotilyzer/gui/app.py — _set_app_mode now calls settings_panel.set_current_mode() to keep the ComboBox in sync with toolbar-driven mode changes.
- spotilyzer/gui/app.py — new _filter_already_analyzed(): pre-flight duplicate check before queuing files for analysis; skips files already analyzed with the currently active model (model_id-aware — re-analysis with a different active model is intentionally allowed, not treated as a duplicate); status bar reports skipped files.
- spotilyzer/gui/app.py — _on_result_ready duplicate guard (2026-06-02) made model_id-aware (path+model_id instead of path-only); previously a re-analysis with a different active model was silently dropped.

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
