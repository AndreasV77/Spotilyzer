# Errata — open documentation defects (Spotilyzer)

Defects found during documentation audits. **Record only.**

Rules:
- An audit pass writes defects here. It does NOT fix them and does NOT propose solutions.
- A separate fix pass works this list top to bottom, one defect at a time.
- A defect's `Status` goes OPEN → FIXED (date + CHANGELOG line). Never delete rows; mark them FIXED so the history stays visible.
- IDs are permanent. Prefix `SP-` = this repo. (`ST-` lives in SpotilyzerTraining/ERRATA.md.)

> Audit of 2026-05-29 **verified against the source eval reports** (Level 1):
> `evaluation_report_..._20260529.json` (BA 63.0 / Hit 86.9 / Flop 67.5 / Mid 34.7)
> and `evaluation_report_..._20260319.json` (BA 64.2 / Hit 82.5 / Flop 73.5 / Mid 36.6),
> both on the 4545-sample holdout. Model files in `models/` verified present at the time:
> both `_20260529` (default) and `_20260319` (alternative) `.joblib` existed.
>
> **Superseded 2026-07-13:** `_20260319` archived to `P:\BACKUP\Archive` (see CHANGELOG.md,
> models/MODEL_COMPARISON.md). Only `_20260529` remains in `models/` as of this date.
> Status below reflects the current file state.

| ID | Found | File | Defect | Status |
|----|-------|------|--------|--------|
| SP-001 | 2026-05-29 | README.md | "Model Performance" shows BA 64.2 / Hit 86.9 / Flop 67.5. No report has this combination: BA 64.2 belongs to `_20260319`, recalls 86.9/67.5 belong to `_20260529`. Describes no real model. | FIXED 2026-05-30 |
| SP-002 | 2026-05-29 | CLAUDE.md | "Predecessor" block lists `_20260319` as the Session-5 model (~8,960 val., BA 63.0 / Hit 72.8 / Flop 68.7). The actual `_20260319` report is the depth=4 **Alternative** (4545 holdout, BA 64.2 / Hit 82.5 / Flop 73.5). Contradicts both the report and this repo's own MODEL_COMPARISON.md. The selectable Alternative is not documented as such anywhere in CLAUDE.md. | FIXED 2026-05-30 |
| SP-003 | 2026-05-29 | CLAUDE.md | "Model search order (GUI)" omits `active_model.txt`. Code reads it between the custom QSettings path and the mtime glob; the documented chain skips it. | FIXED 2026-05-30 |
| SP-004 | 2026-05-29 | CLAUDE.md | The `_20260529` active block (depth=5) is followed by "Optimum at depth=4, col=0.6" with no rationale for why depth=5 is the default. Missing: depth=5 chosen for higher Hit Recall, depth=4 is the BA-optimal alternative. (The rationale already exists in MODEL_COMPARISON.md.) | FIXED 2026-05-30 |
| SP-005 | 2026-05-29 | CLAUDE.md, README.md | Performance metrics are per-30s holdout segment, not per song. Production now averages chunk probabilities over the full track. No note that song-level evaluation is still pending. | FIXED 2026-05-30 |
| SP-006 | 2026-05-29 | CLAUDE.md, README.md | Setup says `models/spotilyzer_model.joblib` "must exist / must be present". The active mechanism is `spotilyzer_model_*.joblib` + `active_model.txt`; the bare `spotilyzer_model.joblib` is only the legacy fallback. Setup instruction is misleading. | FIXED 2026-05-30 |
| SP-007 | 2026-05-29 | models/MODEL_COMPARISON.md | Header says inference architecture is "(Noch zu implementieren in predictor.py / embedder.py)" and lists it as open task #1. It is implemented (commit `aebb131`, 2026-05-29). | FIXED 2026-05-30 |
| SP-008 | 2026-05-29 | models/MODEL_COMPARISON.md | File is written in German. Translation Policy requires English for repository documentation. | FIXED 2026-05-30 |
| SP-009 | 2026-05-29 | README.md | "Package Structure" lists a `training/` folder with active scripts (scout_genre_clusters_deezer.py etc.). CLAUDE.md marks `training/` as DEPRECATED (real training lives in SpotilyzerTraining). | FIXED 2026-05-30 |
| SP-010 | 2026-05-29 | CLAUDE.md | Interface section and "Model file format" note refer to `models/training_report.json`. Actual files are `training_report_MERTv1330M_main+spotify_charts+kworb_{date}.json` (full-named, no bare generic file). If the GUI loads the bare name, metadata stays empty — verify GUI load logic during fix. | FIXED 2026-05-30 |
| SP-011 | 2026-05-30 | spotilyzer/core/pipeline.py | `pipeline.py:74` loads `training_report.json` (bare name). No bare-name file exists in models/; model metadata is silently empty in GUI. Fix: glob for `training_report_*.json` adjacent to the active model file. | FIXED 2026-05-30 |
