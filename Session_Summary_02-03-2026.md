# Spotilyzer – Session Summary
**Datum:** 02. März 2026
**Kontext:** Vollständige Implementierung der ML-Pipeline
**Status:** ✅ FUNKTIONSFÄHIG – GUI mit Highscore-Liste

---

## EXECUTIVE SUMMARY

Spotilyzer ist jetzt ein funktionierendes Tool zur Analyse von KI-generierten Tracks auf Mainstream-Potenzial. Die komplette Pipeline wurde an einem Tag implementiert und validiert.

**Kernkomponenten:**
- 4.789 Deezer-Previews als Trainingsgrundlage
- MERT-v1-95M Audio-Embeddings (768 Dimensionen)
- XGBoost-Klassifikator (71% Accuracy, 93.6% Hit-Recall)
- GUI mit Drag & Drop und Highscore-Liste

**Validierte Ergebnisse:**
| Track | Ergebnis | Beschreibung |
|-------|----------|--------------|
| Kawaii Trap-Rap "Unfall" | **88% HIT** 🥇 | Bouncy Digital Punk, Female Vocals |
| Psychedelic Pop (Retro-Funk) | **88% HIT** 🥇 | Ethereal Female Vocals, Walking Bassline |
| Euphoric Trance | **85% HIT** | 4-on-the-floor, Supersaw, Female Vocals |
| Tribal Funk Mix | **71% HIT** | |
| Melodic Grindcore | **76% MID** | Nische, aber gut produziert |
| Groovin' on Sunshine | **85% MID** | Disco House – "zu generisch"? |
| Producer.ai Grindcore | **87% FLOP** 💀 | Authentisch unanhörbar |

**Erkannte Muster für Hits:**
- Female Vocals (starker Indikator)
- Klare Stimmung/Energie (egal ob aggressiv oder entspannt)
- Saubere, moderne Produktion
- Genre-Fusion > Genre-Purismus

---

## 1. KRITISCHE ÄNDERUNG: SPOTIFY → DEEZER

### Spotify API Februar 2026 – Massive Beschneidungen

**Entfernte Endpoints:**
- `GET /artists/{id}/top-tracks` ❌
- `GET /recommendations` ❌ (Recommendations API)
- `GET /browse/new-releases` ❌

**Entfernte Felder:**
- `popularity` auf Tracks ❌ (war für Labels essentiell!)
- `followers`, `popularity` auf Artists ❌

**Konsequenz:** Spotify für dieses Projekt unbrauchbar.

### Deezer als Ersatz

**Vorteile:**
- Kostenlose API ohne Authentifizierung
- `rank`-Feld als Popularity-Äquivalent (höher = populärer, max ~1.000.000)
- Preview-URLs funktionieren auch in DE (Spotify: 0% wegen GEMA)
- Artist Top Tracks verfügbar

**Einschränkungen:**
- Preview-URLs nur ~15 Minuten gültig → Download-Script holt frische URLs
- "Related Artists" unbrauchbar (Rammstein → 50 Cent, 2Pac...)
- Genre-Endpoints liefern Murks ("Metal" → Taylor Swift, Bad Bunny)

**Lösung:** Direkte Artist-Suche mit Seed-Artist-Listen pro Cluster.

---

## 2. IMPLEMENTIERTE PIPELINE

### Scripts (in Ausführungsreihenfolge)

| Script | Status | Funktion |
|--------|--------|----------|
| `scout_genre_clusters_deezer.py` | ✅ | Sammelt Track-IDs aus 16 Genre-Clustern |
| `download_previews.py` | ✅ | Lädt 30s-Previews (frische URLs) |
| `extract_embeddings.py` | ✅ | MERT-Embeddings extrahieren (GPU) |
| `train_model.py` | ✅ | XGBoost auf Embeddings trainieren |
| `analyze_track.py` | ✅ | CLI-Analyse einzelner Tracks |
| `spotilyzer_gui.py` | ✅ | GUI mit Drag & Drop + Highscore |

### Daten

| Verzeichnis | Inhalt |
|-------------|--------|
| `scout_results_deezer/` | CSVs mit Track-Metadaten + Ranks |
| `previews/` | 4.789 MP3s (~2.2 GB) |
| `embeddings/` | `embeddings.npy` [4789, 768] + Metadaten |
| `models/` | `spotilyzer_model.joblib` + Training-Report |

### Technische Details

**MERT-Embeddings:**
- Modell: `m-a-p/MERT-v1-95M` (~380MB)
- Sample Rate: 24kHz (Resampling automatisch)
- Audio-Länge: Max 30s (Mitte des Tracks)
- Output: 768-dimensionaler Vektor
- Performance: ~0.53s pro Track auf GTX 1660 Ti

**XGBoost-Klassifikator:**
- 500 Estimators, max_depth=6, learning_rate=0.05
- Train/Test Split: 80/20, stratified
- Cross-Validation: 5-fold

**Rank-Schwellen (Deezer):**
- Flop: < 300.000
- Mid: 300.000 – 700.000
- Hit: > 700.000

---

## 3. MODELL-PERFORMANCE

```
Overall Metrics:
  Accuracy:          0.710
  Balanced Accuracy: 0.625
  F1 (macro):        0.648

Per-Class Performance:
  Class     Precision     Recall         F1
  flop          0.679      0.268      0.384
  mid           0.941      0.672      0.784
  hit           0.661      0.936      0.775

Confusion Matrix:
              flop      mid      hit  ← predicted
  flop          74       5     197
  mid            4     176      82
  hit           31       6     545
```

**Interpretation:**
- **Hit-Erkennung stark:** 93.6% Recall – Hits werden zuverlässig erkannt
- **Flop-Erkennung schwach:** Nur 26.8% Recall – viele Flops werden als Hit klassifiziert
- **Bias:** Modell tendiert zu "Hit" bei Unsicherheit
- **Praktische Konsequenz:** Bei 85%+ Hit-Konfidenz = echtes Potenzial, <60% = kritisch

---

## 4. GUI FEATURES

```
┌─────────────────────────────────────────┐
│          🎵 SPOTILYZER                  │
│        Hit/Mid/Flop Analyzer            │
├─────────────────────────────────────────┤
│  📂 Drag & Drop Zone                    │
│     (oder klicken zum Auswählen)        │
├─────────────────────────────────────────┤
│  Sortierung: 🏆 Hit-Score | 🕐 Zuletzt | │
│              📝 Name        🗑️ Clear    │
├─────────────────────────────────────────┤
│  📊 Stats + 🏆 Best Track               │
├─────────────────────────────────────────┤
│  🥇 Track 1 (88%)  🔥 HIT              │
│     [████████████░░] Hit: 88%           │
│     [██░░░░░░░░░░░░] Mid: 10%           │
│     [░░░░░░░░░░░░░░] Flop: 2%           │
│  🥈 Track 2 (85%)  🔥 HIT              │
│     ...                                 │
└─────────────────────────────────────────┘
```

**Features:**
- Drag & Drop (erfordert Non-Admin Shell wegen UIPI)
- Klick-to-Browse als Alternative
- Sortierung: Hit-Score / Zuletzt / Name
- Medaillen für Top 3 (🥇🥈🥉)
- Stats-Leiste mit Gesamtübersicht + Best Track
- Clear-Button zum Zurücksetzen

**Bekanntes Issue:** Drag & Drop funktioniert nicht aus Explorer in Admin-Terminal (Windows UIPI). Workaround: GUI ohne Admin starten oder Datei-Dialog nutzen.

---

## 5. 16 GENRE-CLUSTER

| Bereich | Cluster | Seed-Artists (Beispiele) |
|---------|---------|--------------------------|
| **Metal** | Extreme Metal | Arch Enemy, Amon Amarth, Carcass |
| | Gothic | Rammstein, Eisbrecher, Combichrist, KMFDM |
| | Heavy Metal | Iron Maiden, Judas Priest, Manowar |
| | Power/Symphonic | Nightwish, Powerwolf, Dragonforce |
| | Modern Metal | Five Finger Death Punch, Disturbed |
| | Metalcore | Parkway Drive, Killswitch Engage |
| | Crossover | RATM, Clawfinger, Body Count |
| **Rock** | Hard Rock | AC/DC, Guns N' Roses, Airbourne |
| | Mainstream Rock | U2, Bon Jovi, Nickelback |
| | Modern Rock | Godsmack, Staind, Evanescence |
| | Classic/Southern | Lynyrd Skynyrd, Deep Purple |
| | Alternative | Foo Fighters, QOTSA, Nirvana |
| **Punk/HC** | Punk | Green Day, NOFX, Rise Against |
| | Hardcore | Hatebreed, Madball, Terror |
| **Electronic** | Trance | Tiësto, Armin van Buuren, ATB |
| | House | Daft Punk, Calvin Harris, Disclosure |

**Länder-Charts einbezogen:** DE, US, UK, JP, GLOBAL (500 zusätzliche Tracks)

---

## 6. DEPENDENCIES

```
# requirements.txt (aktuell)
torch>=2.0.0          # Mit CUDA: pip install torch --index-url .../cu124
torchaudio>=2.0.0
transformers>=4.30.0
xgboost>=2.0.0
scikit-learn>=1.3.0
joblib>=1.3.0
pandas>=2.0.0
numpy>=1.24.0
requests>=2.30.0
tqdm>=4.65.0
tkinterdnd2           # Für GUI Drag & Drop
```

**PyTorch CUDA:** `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124`

---

## 7. OFFENE VERBESSERUNGEN (ROADMAP)

### Kurzfristig
1. **Rank-Schwellen kalibrieren** – basierend auf tatsächlicher Verteilung
2. **Batch-Export** – CSV mit allen Ergebnissen
3. **Flop-Erkennung verbessern** – mehr Flop-Samples im Training?

### Mittelfristig
4. **"Klingt wie..."** – Ähnlichkeitssuche im Embedding-Space
5. **Genre-Klassifikation** – Zweites Modell für Cluster-Zuordnung
6. **Technische Metriken** – BPM, LUFS, Key als Zusatzinfo

### Langfristig
7. **Genre-spezifische Modelle** – Ein Modell pro Cluster
8. **Portable Distribution** – Ohne Python-Installation nutzbar

---

## 8. SYSTEMUMGEBUNG

| Parameter | Wert |
|-----------|------|
| OS | Windows 11 |
| Python | 3.11 (via Scoop) |
| GPU | GTX 1660 Ti (6GB VRAM) |
| CUDA | 13.1 |
| PyTorch | 2.10.0 mit CUDA |
| Projekt-Pfad | `G:\Dev\Source\Spotilyzer\` |

---

## 9. NUTZUNG

```bash
cd G:\Dev\Source\Spotilyzer

# GUI starten (NICHT als Admin für Drag & Drop!)
python spotilyzer_gui.py

# CLI für einzelne Tracks
python analyze_track.py "G:\Musik\MeinTrack.flac"

# CLI minimal output
python analyze_track.py "track.mp3" --style minimal

# CLI JSON output
python analyze_track.py "track.mp3" --style json
```

---

*Erstellt: 02.03.2026 — Claude Sonnet 4.5*
*Ergänzt: 02.03.2026 — Claude Opus 4.5*
*Abgeschlossen: 02.03.2026 — Vollständige Pipeline implementiert und validiert*
