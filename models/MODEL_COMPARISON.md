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

## Active Models (as of 2026-05-29)

### Default: `spotilyzer_model_MERTv1330M_main+spotify_charts+kworb_validated_20260529.joblib`

| Metric | Value | Target | Status |
|---|---|---|---|
| **Hit Recall** | **86.9%** | ≥ 80% | ✅ reached |
| **Flop Recall** | **67.5%** | ≥ 50% | ✅ reached |
| **Balanced Accuracy** | **63.0%** | ≥ 65% | ⚠️ −2.0 pp |
| Mid Recall | 34.7% | — | (known weakness) |

- Hyperparameters: depth=5, colsample=0.8
- Training data: 22,722 samples (validated only)
- Holdout: 4,545 samples — 2,999 Hits / 1,131 Mids / 415 Flops

### Alternative: `spotilyzer_model_MERTv1330M_main+spotify_charts+kworb_validated_20260319.joblib`

| Metric | Value | Target | Status |
|---|---|---|---|
| **Hit Recall** | **82.5%** | ≥ 80% | ✅ reached |
| **Flop Recall** | **73.5%** | ≥ 50% | ✅ reached |
| **Balanced Accuracy** | **64.2%** | ≥ 65% | ⚠️ −0.8 pp |
| Mid Recall | 36.6% | — | (known weakness) |

- Hyperparameters: depth=4, colsample=0.6 — BA-optimum from Session 8
- Training data: 22,722 samples (validated only)
- Holdout: 4,545 samples — 2,999 Hits / 1,131 Mids / 415 Flops

**Choice:** Default = higher Hit Recall. Alternative = higher BA + better Flop Recall.

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
| **`MERTv1330M_main+spotify_charts+kworb_validated_20260529`** | **10** | **22,722 val.** | **4,545** | **63.0%** | **86.9%** | **67.5%** |

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
Session 10 (retrain, depth=5):             86.9%  (=)         ← Default model
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

## Holdout Class Distribution

| Class | Samples | Share | Recall (Default) | Recall (Alt.) |
|-------|---------|-------|-----------------|---------------|
| Hit   | 2,999   | 66%   | 86.9%           | 82.5%         |
| Mid   | 1,131   | 25%   | 34.7%           | 36.6%         |
| Flop  | 415     | 9%    | 67.5%           | 73.5%         |

> **Note:** The high Hit share in the holdout (66%) reflects the kworb dataset.
> In real-world use the Hit share will be considerably lower.

---

## Open Tasks

1. **CLAP as second score** — optional in GUI settings (mood/genre dimension)
2. **`compute_labels.py` Bug 3** — Dissent → "contested" instead of "mid" (low priority)
