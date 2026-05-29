# Spotilyzer – Modell-Vergleich

> **Lesehinweis zu den Metriken**
> Alle Metriken auf **echtem Holdout-Set (20 %)** — kein Data-Leakage.
> Quelle: `evaluation_report_*.json` im selben Verzeichnis.
>
> **Inference-Architektur (ab Session 10, 2026-05-29):**
> Full Track → N Chunks à 30s → MERT(chunk_i) → XGBoost(chunk_i) → mean(prob_1..prob_N)
> Jeder Chunk wird einzeln bewertet — identisches Format wie Training (Deezer 30s-Previews).
> *(Noch zu implementieren in `predictor.py` / `embedder.py`)*

---

## Aktive Modelle (Stand: 2026-05-29)

### Default: `spotilyzer_model_MERTv1330M_main+spotify_charts+kworb_validated_20260331.joblib`

| Metrik | Wert | Ziel | Status |
|---|---|---|---|
| **Hit Recall** | **86,9 %** | ≥ 80 % | ✅ erreicht |
| **Flop Recall** | **67,5 %** | ≥ 50 % | ✅ erreicht |
| **Balanced Accuracy** | **63,0 %** | ≥ 65 % | ⚠️ −2,0 pp |
| Mid Recall | 34,7 % | — | (bekannte Schwäche) |

- Hyperparameter: depth=5, colsample=0.8
- Trainingsdaten: 22.722 Samples (validated only)
- Holdout: 4.545 Samples — 2.999 Hits / 1.131 Mids / 415 Flops

### Alternative: `spotilyzer_model_MERTv1330M_main+spotify_charts+kworb_validated_20260319.joblib`

| Metrik | Wert | Ziel | Status |
|---|---|---|---|
| **Hit Recall** | **82,5 %** | ≥ 80 % | ✅ erreicht |
| **Flop Recall** | **73,5 %** | ≥ 50 % | ✅ erreicht |
| **Balanced Accuracy** | **64,2 %** | ≥ 65 % | ⚠️ −0,8 pp |
| Mid Recall | 36,6 % | — | (bekannte Schwäche) |

- Hyperparameter: depth=4, colsample=0.6 — BA-Optimum aus Session 8
- Trainingsdaten: 22.722 Samples (validated only)
- Holdout: 4.545 Samples — 2.999 Hits / 1.131 Mids / 415 Flops

**Wahl:** Default = höherer Hit Recall. Alternative = höhere BA + besserer Flop Recall.

---

## Entwicklung über alle Sessions

| Modell | Session | Datensatz | Holdout | BA | Hit R. | Flop R. |
|--------|---------|-----------|---------|-----|--------|---------|
| `MERTv195M_20260302` | 1 | 5.600 val. | ~1.120 | 62,5 % | 93,6 %* | 26,8 % |
| `MERTv1330M_20260317` | 2 | 8.738 val. | ~1.748 | 51,3 % | 15,2 % | 59,6 % |
| `MERTv195M_validated_20260318` | 3 | 5.262 val. | 967 | 53,2 % | 27,3 % | 68,9 % |
| `MERTv1330M_validated_20260318` | 3 | 5.262 val. | 967 | 57,5 % | 37,5 % | 71,1 % |
| `MERTv195M_main+spotify_charts_validated_20260319` | 4 | 5.660 val. | 1.132 | 57,4 % | 47,7 % | 68,7 % |
| `MERTv1330M_main+spotify_charts_validated_20260319` | 4 | 5.660 val. | 1.132 | 60,9 % | 55,1 % | 69,2 % |
| `MERTv1330M_main+spotify_charts+kworb_validated_20260319` | 5 | 8.960 val. | 1.173 | 63,0 % | 72,8 % | 68,7 % |
| `MERTv1330M_main+spotify_charts+kworb_validated_20260319` | 6 | 22.722 val. | 4.545 | 64,2 % | 82,5 % | 73,5 % |
| **`MERTv1330M_main+spotify_charts+kworb_validated_20260331`** | **8** | **22.722 val.** | **4.545** | 63,0 % | **86,9 %** | 67,5 % |

*\* Session-1-Modell hatte Label-Swap-Bug (hit/mid vertauscht im Report) — Wert nicht direkt vergleichbar.*

---

## Hit-Recall-Entwicklung (330M)

```
Session 2 (8.738 Samples,    626 Hits):  15,2 %
Session 3 (5.262 Samples,    637 Hits):  37,5 %
Session 4 (5.660 Samples,  1.216 Hits):  55,1 %  (+17,6 pp)
Session 5 (8.960 Samples,  3.713 Hits):  72,8 %  (+17,7 pp)
Session 6 (22.722 Samples, 14.991 Hits): 82,5 %  (+9,7 pp)  ✅ Ziel erreicht
Session 8 (depth=5):                     86,9 %  (+4,4 pp)  (Default-Modell)
```

---

## Datensatz-Aufbau (Session 6)

| Quelle | Tracks | Validated | Hits |
|--------|--------|-----------|------|
| main (Deezer-Scouting) | 9.661 | 5.262 | 637 |
| spotify_charts (7 Märkte) | 960 | 960 | 579 |
| kworb (12 Märkte, ≥20M Streams) | ~18.900 | ~18.900 | ~14.000 |
| **Gesamt (dedup)** | **~28.400** | **~22.722** | **~14.991** |

Kworb-Märkte: us, gb, de, jp, br, mx (Session 5) + fr, au, ca (0,85) + it, se, nl (0,70) (Session 6)

---

## Klassenverteilung Holdout

| Klasse | Samples | Anteil | Recall (Default) | Recall (Alt.) |
|--------|---------|--------|-----------------|---------------|
| Hit | 2.999 | 66 % | 86,9 % | 82,5 % |
| Mid | 1.131 | 25 % | 34,7 % | 36,6 % |
| Flop | 415 | 9 % | 67,5 % | 73,5 % |

> **Hinweis:** Der hohe Hit-Anteil im Holdout (66 %) spiegelt den kworb-Datensatz wider.
> In der realen Nutzung wird der Hit-Anteil deutlich niedriger sein.

---

## Offene Aufgaben

1. **Inference-Architektur implementieren** — `predictor.py` / `embedder.py` in Spotilyzer:
   per-chunk XGBoost + mean(probabilities) statt mean-pool(embeddings) → XGBoost
2. **CLAP als zweiter Score** — optional in GUI-Einstellungen (Mood/Genre-Dimension)
3. **`compute_labels.py` Bug 3** — Dissent → "contested" statt "mid" (geringe Priorität)
