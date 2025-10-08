# Music Analysis Toolkit (Spotify Web API + Local MIR)

This mini toolkit gives you two complementary paths:

A) **Spotify Web API (Spotipy)** — pull objective audio features for *reference/benchmark tracks* available on Spotify (danceability, energy, valence, tempo, loudness, etc.).  
B) **Local MIR (librosa + pyloudnorm)** — extract comparable features from your **own audio files** (e.g., Tunee renders not on Spotify yet).

Use A to understand mainstream trends and set target ranges. Use B to analyze your tracks and compare.

---

## 0) Setup

### Python packages (create a venv if you like)
```bash
pip install spotipy python-dotenv pandas numpy librosa pyloudnorm
```

> If `librosa` installation complains about ffmpeg, install ffmpeg via your package manager.
> On Windows, you can use e.g. `winget install Gyan.FFmpeg` or download from ffmpeg.org.

### Environment variables (recommended via `.env`)
Copy `.env.example` to `.env` and fill in your **Spotify** credentials.

- `SPOTIPY_CLIENT_ID` — from Spotify Developer Dashboard
- `SPOTIPY_CLIENT_SECRET` — from Spotify Developer Dashboard
- `SPOTIPY_REDIRECT_URI` — use explicit IP loopback, e.g. `http://127.0.0.1:8888/callback`

> Tip: For Windows PowerShell (temporary session):
> ```powershell
> $env:SPOTIPY_CLIENT_ID="YOUR_ID"
> $env:SPOTIPY_CLIENT_SECRET="YOUR_SECRET"
> $env:SPOTIPY_REDIRECT_URI="http://127.0.0.1:8888/callback"
> ```

---

## 1) Test Spotify auth
```bash
python3 spotify_auth_test.py
```
It opens a browser for OAuth. After login, the script prints your display name and a token sanity check.

---

## 2) Fetch Spotify audio features (batch)

**Option 1: by Track IDs/URLs**  
Fill `input_spotify_tracks.csv` with a column `track` that contains either Spotify track IDs or full URLs.

Run:
```bash
python3 spotify_audio_features_batch.py --in input_spotify_tracks.csv --out spotify_features.csv
```

**Option 2: by Search Queries (title + artist)**  
Fill `input_spotify_search.csv` with columns `title` and `artist`.  
The script finds the top Spotify match and fetches the features.

Run:
```bash
python3 spotify_audio_features_batch.py --search input_spotify_search.csv --out spotify_features.csv
```

The output includes typical Spotify audio features (danceability, energy, valence, tempo, loudness, key, mode, time_signature, speechiness, instrumentalness, liveness, acousticness) plus Spotify popularity.

---

## 3) Analyze local audio files (your Tunee renders)

Put WAV/MP3/FLAC files into `./local_audio/` (or anywhere). Then run:
```bash
python3 local_audio_features.py --in ./local_audio --out local_features.csv
```

This extracts:
- duration (s), tempo (BPM), estimated key (rough), spectral centroid mean, RMS loudness (approx), integrated LUFS (pyloudnorm), short-time energy variance (as a proxy for dynamics).

> Key detection is a rough estimation. For more robust results, consider Essentia’s key extractor.

---

## 4) Compare & rank

Use `compare_and_rank.ipynb` (Jupyter) or your own spreadsheet:
- Load `spotify_features.csv` as **reference** (mainstream targets per genre).
- Load `local_features.csv` as **candidates**.
- Create a simple score: e.g. z-score distance to target ranges + bonus for hook density (if annotated) + penalty for extreme loudness, etc.

You can iterate weights per round (Round 1 → Round 2 → Round 3).

---

## Notes
- Spotify features are **catalog-based**. They won’t exist for private/unreleased tracks. That’s why local MIR is essential.
- For better genre priors, you can cluster Spotify reference tracks and compute **centroids**; then score your tracks by distance to the centroid of your target cluster.
- If you prefer not to install `librosa`, you can still do LUFS-only analysis via `pyloudnorm` (requires raw audio time series), but you’ll miss tempo/key.
