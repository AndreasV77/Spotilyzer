# Spotilyzer – Model Comparison

> **Notes on metrics**
> All metrics on **real holdout set (20%)** — no data leakage.
> Source: `evaluation_report_*.json` in this directory.
>
> **Inference architecture (from Session 10, 2026-05-29):**
> Full Track → N chunks × 30s → MERT(chunk_i) → XGBoost(chunk_i) → mean(prob_1..prob_N)
> Each chunk is scored independently — identical format to training (Deezer 30s previews).
> Implemented in `predictor.py` / `embedder.py` (commit `aebb131`, 2026-05-29).

---

## Active Models (as of 2026-07-13)

### Currently deployed: `spotilyzer_model_MERTv1330M_depth4refresh_main+spotify_charts+kworb_validated_20260713.joblib` (SLYZR 1.3)

| Metric | Value | Target | Status |
|---|---|---|---|
| **Balanced Accuracy** | **64.3%** | ≥ 65% | ⚠️ −0.7 pp |
| **Hit Recall** | **82.4%** | ≥ 80% | ✅ reached |
| **Flop Recall** | **74.5%** | ≥ 50% | ✅ reached |
| Mid Recall | 36.0% | — | (known weakness) |

- Hyperparameters: depth=4, colsample=0.6 — standing default (`SpotilyzerTraining/configs/training.yaml`)
- Training data: 24,170 samples (validated only; Kworb + Spotify Charts refreshed 2026-07-13)
- Holdout: 4,834 samples

**2026-07-13 decision:** depth=5/col=0.8 (previously deployed as `_20260529`, SLYZR 1.2) judged
a taste-call trade — a few points of Hit Recall for lower BA/Flop Recall/confidence — not a
technical win. depth=4/col=0.6 is the standing hyperparameter default going forward. `_20260529`
retired to `P:\BACKUP\Archive\Spotilyzer_model_20260529_retired_2026-07-13.zip`. Full sweep on
fresh data (24,170 validated samples) before deciding:

| Config | BA | Hit R. | Flop R. |
|---|---|---|---|
| **depth=4/col=0.6 (deployed, SLYZR 1.3)** | **64.3%** | 82.4% | 74.5% |
| depth=4/col=0.7 | 64.5% | 82.8% | 74.7% |
| depth=4/col=0.8 | 64.7% | 82.8% | 75.2% |
| depth=3/col=0.8 (kept for manual spot-testing) | 65.3% (first ≥65% BA) | 79.4% | 81.0% |
| depth=5/col=0.7 | 63.1% | 86.3% | 69.6% |
| depth=5/col=0.8 (= old `_20260529` config, refreshed) | 62.2% | 86.5% | 67.7% |

Final triage kept only `depth4refresh` (deployed) and `d3c08` (depth=3/col=0.8, the only config
crossing BA≥65%, kept in `SpotilyzerTraining/outputs/models/` for manual testing on varied
tracks — not a deploy candidate yet). The other four offered no distinct trade-off point beyond
this table and were archived to `P:\BACKUP\Archive\Spotilyzer_model_archive_2026-07-13_batch2.zip`.

---

## Development Across All Sessions

| Model | Session | Dataset | Holdout | BA | Hit R. | Flop R. |
|--------|---------|---------|---------|-----|--------|---------|
| `MERTv195M_20260302` | 1 | 5,600 val. | ~1,120 | 62.5% | 93.6%* | 26.8% |
| `MERTv1330M_20260317` | 2 | 8,738 val. | ~1,748 | 51.3% | 15.2% | 59.6% |
| `MERTv195M_validated_20260318` | 3 | 5,262 val. | 967 | 53.2% | 27.3% | 68.9% |
| `MERTv1330M_validated_20260318` | 3 | 5,262 val. | 967 | 57.5% | 37.5% | 71.1% |
| `MERTv195M_main+spotify_charts_validated_20260319` | 4 | 5,660 val. | 1,132 | 57.4% | 47.7% | 68.7% |
| `MERTv1330M_main+spotify_charts_validated_20260319` | 4 | 5,660 val. | 1,132 | 60.9% | 55.1% | 69.2% |
| `MERTv1330M_main+spotify_charts+kworb_validated_20260319` | 5 | 8,960 val. | 1,173 | 63.0% | 72.8% | 68.7% |
| `MERTv1330M_main+spotify_charts+kworb_validated_20260319` | 6 | 22,722 val. | 4,545 | 64.2% | 82.5% | 73.5% |
| `MERTv1330M_main+spotify_charts+kworb_validated_20260331` | 8 | 22,722 val. | 4,545 | 63.0% | 86.9% | 67.5% |
| `MERTv1330M_main+spotify_charts+kworb_validated_20260529` (retired 2026-07-13) | 10 | 22,722 val. | 4,545 | 63.0% | 86.9% | 67.5% |
| **`MERTv1330M_depth4refresh_main+spotify_charts+kworb_validated_20260713`** | **11** | **24,170 val.** | **4,834** | **64.3%** | **82.4%** | **74.5%** |

*\* Session-1 model had a label-swap bug (hit/mid swapped in report) — value not directly comparable.*

---

## Hit Recall Development (330M)

```
Session 2  (8,738 samples,     626 Hits):  15.2%
Session 3  (5,262 samples,     637 Hits):  37.5%
Session 4  (5,660 samples,   1,216 Hits):  55.1%  (+17.6 pp)
Session 5  (8,960 samples,   3,713 Hits):  72.8%  (+17.7 pp)
Session 6  (22,722 samples, 14,991 Hits):  82.5%  (+9.7 pp)   ✅ Target reached
Session 8  (depth=5):                      86.9%  (+4.4 pp)
Session 10 (retrain, depth=5):             86.9%  (=)         ← retired 2026-07-13
Session 11 (24,170 samples, depth=4):      82.4%  (-4.5 pp)   ← deployed (BA-priority, not Hit-Recall-priority)
```

---

## Dataset Composition (Session 6)

| Source | Tracks | Validated | Hits |
|--------|--------|-----------|------|
| main (Deezer scouting) | 9,661 | 5,262 | 637 |
| spotify_charts (7 markets) | 960 | 960 | 579 |
| kworb (12 markets, ≥20M streams) | ~18,900 | ~18,900 | ~14,000 |
| **Total (dedup)** | **~28,400** | **~22,722** | **~14,991** |

Kworb markets: us, gb, de, jp, br, mx (Session 5) + fr, au, ca (0.85) + it, se, nl (0.70) (Session 6)

---

## Holdout Class Distribution (2026-07-13, 4,834 samples)

| Class | Samples | Share | Recall (deployed, depth=4/col=0.6) |
|-------|---------|-------|-----------------|
| Hit   | 3,196   | 66%   | 82.4%           |
| Mid   | 1,223   | 25%   | 36.0%           |
| Flop  | 415     | 9%    | 74.5%           |

> **Note:** The high Hit share in the holdout (66%) reflects the kworb dataset.
> In real-world use the Hit share will be considerably lower.

---

## Open Tasks

1. **CLAP as second score** — optional in GUI settings (mood/genre dimension)
2. **`compute_labels.py` Bug 3** — Dissent → "contested" instead of "mid" (low priority)
