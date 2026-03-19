# Spotilyzer v2.0 — Hit/Mid/Flop Analyzer

ML-basiertes Audio-Analyse-Tool. Klassifiziert Tracks als **Hit / Mid / Flop** anhand von Mainstream-Kompatibilität.

**Pipeline:** Audiodatei → MERT-v1-330M Embeddings (1024-dim) → XGBoost 3-Klassen-Klassifikator → GUI oder CLI

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

Trainiert auf **~8.960 validated Samples** (Deezer 30s-Previews + Spotify Charts + Kworb historische Charts, 6 Märkte), 1024-dim MERT-v1-330M Embeddings. Holdout-Set: 1173 Samples (20%).

| Metrik            | Wert           |
|-------------------|----------------|
| Balanced Accuracy | **63,0 %**     |
| Hit Recall        | **72,8 %**     |
| Flop Recall       | **68,7 %** ✓  |

**Interpretation:** ≥ 85 % Confidence = echtes Potential. < 60 % = unsicher, als Mid behandeln.
Inferenz: ~0,8 s/Track auf GTX 1660 Ti. Hit Recall verbessert sich kontinuierlich — aktuell 72,8 % (Ziel ≥ 80 %).

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

Das Training läuft im separaten Repository [SpotilyzerTraining](https://github.com/AndreasV77/SpotilyzerTraining).

**Datenquellen:**
- **Deezer API** — 30s-Previews + Popularity-Rank (kostenlos, keine Auth)
- **Last.fm API** — Playcount + Listeners zur Label-Validierung
- **Spotify Charts CSV** — Top 200 Charts (manuell, 7 Märkte)
- **Kworb.net** — Historische Chart-Daten (peak_position, weeks_in_chart)
- **MusicBrainz API** — ISRC-Lookup für Deduplizierung

**Aktueller Datensatz:** 5.660 validated Samples, 1.216 Hits, 23 Genre-Cluster + Charts

**Deployment:**
```powershell
# Nach Training in SpotilyzerTraining:
Copy-Item outputs/models/spotilyzer_model_MERTv1330M_*_validated_*.joblib ..\Spotilyzer\models\
Copy-Item outputs/reports/training_report_MERTv1330M_*_validated_*.json   ..\Spotilyzer\models\
```

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
