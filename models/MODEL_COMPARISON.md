# Spotilyzer – Modell-Vergleich

> **Lesehinweis zu den Metriken**
> Alle Metriken auf **echtem Holdout-Set (20 %)** — kein Data-Leakage.
> Quelle: `evaluation_report_*.json` im selben Verzeichnis.

---

## Aktives Modell (Stand: 2026-03-19)

**`spotilyzer_model_MERTv1330M_main+spotify_charts+kworb_validated_20260319.joblib`**

| Metrik | Wert | Ziel | Status |
|---|---|---|---|
| **Hit Recall** | **82,5 %** | ≥ 80 % | ✅ erreicht |
| **Flop Recall** | **73,5 %** | ≥ 50 % | ✅ erreicht |
| **Balanced Accuracy** | **64,2 %** | ≥ 65 % | ⚠️ −0,8 pp |
| Mid Recall | 36,6 % | — | (bekannte Schwäche) |

- Embedder: MERT-v1-330M (1024-dim)
- Trainingsdaten: 22.722 Samples (validated only)
- Holdout: 4.545 Samples — 2.999 Hits / 1.131 Mids / 415 Flops
- CV Balanced Accuracy: 63,4 % ± 0,9 % (konsistent, kein Overfitting)

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
| **`MERTv1330M_main+spotify_charts+kworb_validated_20260319`** | **6** | **22.722 val.** | **4.545** | **64,2 %** | **82,5 %** | **73,5 %** |

*\* Session-1-Modell hatte Label-Swap-Bug (hit/mid vertauscht im Report) — Wert nicht direkt vergleichbar.*

---

## Hit-Recall-Entwicklung (330M)

```
Session 2 (8.738 Samples,    626 Hits):  15,2 %
Session 3 (5.262 Samples,    637 Hits):  37,5 %
Session 4 (5.660 Samples,  1.216 Hits):  55,1 %  (+17,6 pp)
Session 5 (8.960 Samples,  3.713 Hits):  72,8 %  (+17,7 pp)
Session 6 (22.722 Samples, 14.991 Hits): 82,5 %  (+9,7 pp)  ✅ Ziel erreicht
```

**Empirische Regel:** Je ~2.500 neue validierte Hit-Samples → ca. +17–18 pp Hit Recall
(gültig für Session 3–5; Session 6 bestätigt den Trend mit größerem Sprung)

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

## Klassenverteilung Holdout (Session 6)

| Klasse | Samples | Anteil | Recall | Precision |
|--------|---------|--------|--------|-----------|
| Hit | 2.999 | 66 % | 82,5 % | 81,1 % |
| Mid | 1.131 | 25 % | 36,6 % | 44,1 % |
| Flop | 415 | 9 % | 73,5 % | 54,8 % |

> **Hinweis:** Der hohe Hit-Anteil im Holdout (66 %) spiegelt den kworb-Datensatz wider,
> der primär Top-Streaming-Tracks enthält. In der realen Nutzung (Analyse unbekannter Tracks)
> wird der Hit-Anteil deutlich niedriger sein.

---

## Bekannte Schwächen

| Problem | Ursache | Auswirkung |
|---------|---------|------------|
| Mid Recall nur 36,6 % | Mid-Klasse zwischen Hit/Flop zerrieben | 539 Mids werden als Hit klassifiziert |
| BA knapp unter 65 % (64,2 %) | Mid-Recall zieht BA runter | Primärziel noch nicht ganz erreicht |
| Klassenverteilung schief (66 % Hits) | kworb liefert fast nur Hits | Modell leicht hit-gebias'd |

---

## Stärken & Schwächen im Vergleich

| | **MERTv195M (S1)** | **MERTv1330M (S3)** | **MERTv1330M (S6, aktiv)** |
|---|---|---|---|
| Hit-Erkennung | ✅ 93,6 %* | ⚠️ 37,5 % | ✅ **82,5 %** |
| Flop-Erkennung | ❌ 26,8 % | ✅ 71,1 % | ✅ **73,5 %** |
| Mid-Erkennung | ✅ 67,2 % | ✅ ~46 % | ⚠️ 36,6 % |
| Balanced Accuracy | 62,5 % | 57,5 % | **64,2 %** |
| Label-Swap-Bug | ⚠️ | ✅ behoben | ✅ |
| Produktionsstatus | ❌ | ❌ | ✅ **deployed** |

*\* Label-Swap-Bug — Wert nicht direkt vergleichbar*

---

## Nächste Schritte (nach Session 6)

1. **BA ≥ 65 %** — fehlen noch 0,8 pp; Optionen:
   - Hyperparameter-Tuning (Mid-Klasse stärken)
   - Mid-Samples ausbalancieren (Oversampling / Untergewichtung der Hit-Flut)
   - `compute_labels.py` Bug 3 fixen (Dissent → "contested" statt "mid")
2. **Neue Chart-Quellen** — ODJC (DJ Charts CSV), aCharts (nach Bedarf)
3. **`enrich_isrc.py`** — ISRC für kworb-Tracks via MusicBrainz nachfüllen
