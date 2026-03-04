# Spotilyzer v2.0 — Hit/Mid/Flop Analyzer

ML-basiertes Audio-Analyse-Tool. Klassifiziert Tracks als **Hit / Mid / Flop** anhand von Mainstream-Kompatibilität.

**Pipeline:** Audiodatei → MERT-v1-95M Embeddings (768-dim) → XGBoost 3-Klassen-Klassifikator → GUI oder CLI

---

## Schnellstart

```bash
# Venv erstellen & aktivieren (Python 3.12 empfohlen, min. 3.10)
python -m venv .venv312
.\.venv312\Scripts\Activate.ps1   # PowerShell

# Paket installieren
pip install -e .

# GUI starten
spotilyzer

# CLI — einzelnen Track analysieren
spotilyzer-cli "mein_track.mp3"
```

> **Erster Start:** MERT-v1-95M (~380 MB) wird automatisch von HuggingFace heruntergeladen
> und in `~/.cache/huggingface/hub/` gecacht. Internetverbindung erforderlich.

> **Modell erforderlich:** `models/spotilyzer_model.joblib` muss vorhanden sein.
> Entweder selbst trainieren (siehe [Training](#training)) oder eine fertige Version herunterladen.

---

## Features

- **GUI** (PySide6): Drag & Drop, drei View-Modi (Simple / Balanced / Pro), Dark/Light-Theme
- **CLI**: JSON, Minimal oder Default-Ausgabe; `--device cuda` für GPU
- **13 Analyse-Felder** pro Track: Rating, Confidence, Hit/Mid/Flop-Wahrscheinlichkeiten + BPM, LUFS, Key, Format, Sample Rate, Bitrate, Kanäle, Dauer, Dateigröße
- **Unterstützte Formate:** `.mp3` `.flac` `.wav` `.ogg` `.m4a` `.aac` `.wma`

---

## Modell-Performance (aktuell)

Trainiert auf **5.600 Samples** (Deezer 30s-Previews + Charts), 768-dim MERT-Embeddings.

| Metrik            | Wert           |
|-------------------|----------------|
| Accuracy          | 71,0 %         |
| Balanced Accuracy | 62,5 %         |
| F1 macro          | 64,8 %         |
| Hit Recall        | **93,6 %** ✓  |
| Flop Recall       | 26,8 % (schwach)|
| Mid Precision     | 94,1 % ✓      |

**Interpretation:** ≥ 85 % Confidence = echtes Potential. < 60 % = unsicher, als Mid behandeln.
Inferenz: ~0,53 s/Track auf GTX 1660 Ti.

---

## CLI-Referenz

```bash
# Standard-Ausgabe (Tabelle)
spotilyzer-cli "track.mp3"

# JSON (maschinenlesbar)
spotilyzer-cli "track.mp3" --style json

# Minimal (nur Rating + Score)
spotilyzer-cli "track.mp3" --style minimal

# GPU verwenden
spotilyzer-cli "track.mp3" --device cuda

# Ohne Audio-Infos (schneller)
spotilyzer-cli "track.mp3" --no-audio-info
```

---

## Setup (Entwicklung)

```bash
# Nur Core
pip install -e .

# Mit Training-Deps (XGBoost, scikit-learn, transformers, torchaudio …)
pip install -e ".[training]"

# Mit Dev-Deps (pyinstaller, pytest)
pip install -e ".[dev]"
```

---

## Training

Das Training nutzt **Deezer** als Datenquelle (kostenlose, unauthentifizierte API mit `rank`-Feld
als Popularitäts-Proxy). Spotify wurde im Februar 2026 als Quelle aufgegeben, da die API
`/audio-features`, Track-Popularity und die Recommendations-Endpoint entfernt hat.

### Trainingsdaten-Pipeline (in dieser Reihenfolge)

```bash
# 1. Tracks scouten (Deezer API → CSV mit Track-IDs und Ranks)
python training/scout_genre_clusters_deezer.py --save-tracks

# 2. Previews herunterladen (30s-MP3s von Deezer, ~2,2 GB)
#    WICHTIG: Deezer Preview-URLs laufen nach ~15 Min ab — immer frisch holen!
python training/download_previews.py

# 3. MERT-Embeddings extrahieren (GPU empfohlen: <1s/Track, CPU: ~10-15s/Track)
python training/extract_embeddings.py

# 4. XGBoost-Modell trainieren
python training/train_model.py
```

**Ausgabe:** `models/spotilyzer_model.joblib` + `models/training_report.json`

### Externe Datenpfade (optional)

Standardmäßig landen alle Trainingsdaten im Projektordner. Für externe Festplatten oder
andere Verzeichnisse:

```bash
# Vorlage kopieren
cp training/paths.env.example training/paths.env

# Pfade in training/paths.env anpassen:
# SPOTILYZER_PREVIEWS_DIR=E:/Spotilyzer-Data/previews
# SPOTILYZER_EMBEDDINGS_DIR=E:/Spotilyzer-Data/embeddings
# … etc.

# Aktive Pfade prüfen
python training/config.py
```

`training/paths.env` ist gitignored (lokale Maschinenpfade). CLI-Argumente der Skripte
überschreiben die Pfade aus `paths.env` immer.

### 16 Genre-Cluster

Extreme Metal · Gothic · Heavy Metal · Power/Symphonic · Modern Metal · Metalcore ·
Crossover · Hard Rock · Mainstream Rock · Modern Rock · Classic/Southern Rock ·
Alternative · Punk · Hardcore · Trance · House

Zusätzlich: Länder-Charts (DE, US, UK, JP, GLOBAL) mit ~500 Extra-Tracks.

### Rank-Schwellen (Deezer)

| Rating | Deezer Rank        |
|--------|--------------------|
| Flop   | < 300.000          |
| Mid    | 300.000 – 700.000  |
| Hit    | > 700.000          |

---

## Paketstruktur

```
spotilyzer/          # Installierbares Paket
  core/
    pipeline.py      # AnalysisPipeline — orchestriert Embedder + Predictor + AudioInfo
    embedder.py      # MERTEmbedder (Singleton) — MERT-v1-95M, 768-dim
    predictor.py     # SpotilyzerPredictor — XGBoost-Wrapper
    audio_info.py    # BPM, LUFS, Key, Format, Waveform
  cli/
    analyze.py       # CLI-Einstiegspunkt
  gui/
    app.py           # SpotilyzerApp (QMainWindow)
    central.py       # DropZone + Ergebnisliste + Stats
    worker.py        # QThread-Worker für ML-Operationen
    theme.py         # ThemeManager (Dark/Light + Accent-Farbe)
    panels/          # Dock-Panels: file, highscore, history, tech, settings
    widgets/         # DropZone, ResultCard, ConfidenceBar, Waveform
  data/
    models.py        # AnalysisResult, AudioInfo, Rating/AppMode/SortMode
    persistence.py   # JSON/CSV/MD/TXT-Export, Auto-Save
training/            # Nicht im EXE gebündelt
  scout_genre_clusters_deezer.py
  download_previews.py
  extract_embeddings.py
  train_model.py
  config.py          # Pfad-Konfiguration (liest paths.env)
  paths.env.example  # Vorlage für externe Datenpfade
models/              # spotilyzer_model.joblib + training_report.json
resources/           # GUI-Assets
legacy/              # Archivierte Spotify-API-Skripte (nur Referenz)
```

---

## Windows EXE bauen

```bash
pip install -e ".[dev]"
pyinstaller spotilyzer.spec

# CUDA-Libs entfernen (~1,5 GB Einsparung)
python strip_cuda.py
```

MERT (~380 MB) wird **nicht** gebündelt — wird beim ersten Start heruntergeladen.
Gesamtgröße nach Strip: ~3 GB.

---

## Bekannte Einschränkungen

- **App-Icon:** `resources/spotilyzer.ico` fehlt noch — Fenster zeigt Standard-Qt-Icon
- **Drag & Drop + Admin-Shell (Windows):** D&D aus Explorer funktioniert nicht wenn die App
  in einer elevated Shell läuft (Windows UIPI). Lösung: App ohne Admin starten oder
  Datei-Dialog verwenden
- **Flop-Recall schwach (26,8 %):** Mehr Flop-Trainingssamples benötigt

---

## Roadmap

**Kurzfristig**
- App-Icon erstellen (`resources/spotilyzer.ico`)
- Flop-Recall verbessern (mehr Flop-Samples)
- Modell-Download im GUI (statt lokales Training)

**Mittelfristig**
- "Klingt wie …" — Ähnlichkeitssuche im Embedding-Raum
- Genre-Klassifikation (zweites Modell)
- Genre-Cluster-Editor im GUI (PRO-Modus)

**Langfristig**
- Genre-spezifische Modelle (eines pro Cluster)
