# Spotilyzer – Modell-Vergleich

> **Lesehinweis zu den Metriken**
> - *Holdout* = 20 % Test-Split (ehrlich, für Vergleiche relevant)
> - *Full-Data* = gesamter Datensatz (immer inflationiert durch Overfitting, nur zur Orientierung)

---

## Übersicht

| | **MERTv195M · 2026-03-02** | **MERTv1330M · 2026-03-17** | **Ziel** |
|---|---|---|---|
| **Datei** | `spotilyzer_model_MERTv195M_20260302.joblib` | `spotilyzer_model_MERTv1330M_20260317.joblib` | — |
| **Embedder** | MERT-v1-95M | MERT-v1-330M | — |
| **Embedding-Dim** | 768 | 1024 | — |
| **Trainingsdaten** | 5 600 Samples | 8 738 Samples | ≥ 10 000 |
| **Datenquellen** | Deezer-Cluster + Charts (DE, US, UK) | + FR, BR, ES | + IT, MX, CA, AU, … |

---

## Klassenverteilung (Training)

| Klasse | 95M-Modell | 330M-Modell | Anmerkung |
|---|---|---|---|
| Hit | 1 308 (23,4 %) | 626 (7,2 %) | ⚠ stark gesunken — Hauptproblem |
| Mid | 2 911 (52,0 %) | 6 022 (68,9 %) | überrepräsentiert |
| Flop | 1 381 (24,7 %) | 2 090 (23,9 %) | ok |

---

## Metriken (Holdout-Testset, 20 %)

| Metrik | 95M-Modell | 330M-Modell | Ziel |
|---|---|---|---|
| **Accuracy** | 71,0 % | 69,9 % | — |
| **Balanced Accuracy** | 62,5 % | 51,3 % ❌ | ≥ 65 % |
| **F1 Macro** | 64,8 % | 51,6 % ❌ | — |
| **CV Balanced Acc** | 64,8 % ± 1,3 % | 50,3 % ± 1,7 % | — |

### Per-Klasse (Holdout)

| | Hit Recall | Hit Prec. | Mid Recall | Mid Prec. | Flop Recall | Flop Prec. |
|---|---|---|---|---|---|---|
| **95M-Modell** | **93,6 %** ✅ | 66,1 % | 67,2 % | 94,1 % | 26,8 % ❌ | 67,9 % |
| **330M-Modell** | 15,2 % ❌❌ | 27,1 % | 79,2 % | 78,4 % | **59,6 %** ✅ | 54,0 % |
| **Ziel** | ≥ 80 % | — | — | — | ≥ 50 % | — |

---

## Evaluation auf Gesamtdaten (inflationiert – nicht für Vergleiche nutzen)

| Metrik | 330M-Modell (Full-Data) |
|---|---|
| Accuracy | 91,8 % |
| Balanced Accuracy | 89,2 % |
| Hit Recall | 83,1 % |
| Flop Recall | 91,9 % |
| Mid Recall | 92,6 % |

*(Zeigt Overfitting-Potential des Modells, keine echte Generalisierung)*

---

## Stärken & Schwächen

| | 95M-Modell | 330M-Modell |
|---|---|---|
| Hit-Erkennung | ✅ Sehr stark (93,6 % Recall) | ❌ Kaputt (15,2 %) |
| Flop-Erkennung | ❌ Schwach (26,8 %) | ✅ Besser (59,6 %) |
| Mid-Erkennung | ✅ Präzise (94,1 % Prec.) | ✅ Solide |
| Bias | Tendiert zu "Hit" | Tendiert zu "Mid" |
| Label-Swap-Bug | ⚠ Vorhanden (hit/mid vertauscht) | ✅ Behoben |
| Klassengewichte | ✗ Keine | ✅ Balanced + Robustness |
| Robustness-Labels | ✗ Nein | ✅ Validated / Contested |

---

## Warum ist der 330M-Hit-Recall so schlecht?

Das 95M-Modell hatte 1 308 Hit-Samples (23,4 % des Datensatzes).
Das 330M-Modell hat nur noch 626 (7,2 %) — obwohl der Datensatz größer wurde.

Die neu gescouteten Länder (FR, BR, ES) haben vor allem Mid/Flop-Tracks geliefert.
`compute_sample_weight("balanced")` kann das kompensieren, aber nicht überwinden wenn
die absolute Stichprobenzahl zu klein ist (626 Samples für eine von drei Klassen).

**Lösung:** Mehr echte Hit-Samples. Ziel ≥ 2 000 Hits (aktuell 626).
Empfehlung: weitere Länder-Charts (IT, MX, CA, AU, JP) + ggf. iTunes RSS-Charts.

---

## Wann welches Modell verwenden?

| Anwendungsfall | Empfehlung |
|---|---|
| Hits zuverlässig erkennen (wenig False Negatives) | 95M-Modell *(trotz Label-Bug beim Report)* |
| Flops aussieben | 330M-Modell |
| Allgemein / aktuell empfohlen | **330M-Modell** sobald Hit-Recall ≥ 80 % erreicht |
| Produktion | keines von beiden bisher — Ziele noch nicht erfüllt |

---

## Nächste Schritte

1. **Mehr Hit-Samples** — IT, MX, CA, AU, JP, AR Charts scouten (Ziel: ≥ 2 000 Hits)
2. **Ggf. iTunes RSS** — kostenlose JSON-Feeds, kein Auth nötig, hit-dicht
3. Neu trainieren → Ziel: Hit Recall ≥ 80 %, Flop Recall ≥ 50 %, BA ≥ 65 %
4. Label-Schwellenwerte (`thresholds.yaml`) kalibrieren (Last.fm-Werte noch ungeprüft)
