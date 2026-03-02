# CLAUDE.md — AI Assistant Guide for Spotilyzer

This file provides context for AI assistants (Claude, Copilot, etc.) working in this repository.

---

## Project Overview

**Spotilyzer** is a Python CLI toolkit for music audio feature analysis. It combines:

- **Spotify Web API** integration (public/private playlists, recommendations, audio features)
- **Local MIR** (Music Information Retrieval) via `librosa` and `pyloudnorm`
- **Statistical ranking** engine (Z-score-based cluster matching)
- **Multi-market support** (DE, US, GB) with data merging capabilities

**Language**: Python 3.12
**Type**: Batch/CLI data pipeline — no web server, no database
**Output**: CSV files written to `output/`

---

## Repository Structure

```
Spotilyzer/
├── .github/
│   └── workflows/
│       ├── claude.yml                    # Claude Code action (PR/issue comments)
│       └── claude-code-review.yml        # Automated PR review workflow
├── input/
│   ├── input_spotify_search.csv          # Search inputs: title, artist columns
│   ├── input_spotify_tracks.csv          # Track inputs: URL or Spotify ID
│   └── playlist_ids.txt                  # Default playlist IDs (comments with #)
├── output/                               # Generated CSVs (git-ignored)
│   └── refdata/                          # Reference stats CSVs
├── local_audio/                          # Local audio files to analyze (git-ignored)
├── .env.example                          # Required env vars template
├── requirements.txt                      # Python dependencies
├── README.md                             # English setup & usage guide
├── RUNBOOK.md                            # German step-by-step runbook
├── RUNBOOK.ps1                           # PowerShell helper functions (Windows)
│
# --- Core Python scripts ---
├── spotify_auth_test.py                  # OAuth sanity check (run first)
├── spotify_playlist_features.py          # Main playlist harvester (multi-market)
├── example_playlist_pull.py              # Robust single-playlist puller (with fallbacks)
├── spotify_audio_features_batch.py       # Batch track feature extraction (CSV input)
├── local_audio_features.py              # MIR analysis of local audio files
├── build_genre_ref_stats.py             # Build reference clusters from Recommendations API
└── score_rank.py                         # Z-score ranking against reference clusters
```

---

## Dependencies

Install via:
```bash
pip install -r requirements.txt
```

**Core dependencies** (`requirements.txt`):
| Package | Version | Purpose |
|---------|---------|---------|
| `spotipy` | 2.24.0 | Spotify Web API client |
| `python-dotenv` | 1.0.1 | Load `.env` variables |
| `pandas` | 2.2.2 | Data manipulation & CSV I/O |
| `requests` | 2.32.3 | HTTP client (used by spotipy) |
| `tqdm` | 4.66.4 | Progress bars in CLI output |
| `pytest` | 8.3.2 | Testing framework |

**Optional dependencies** (install separately for local MIR features):
- `librosa` — tempo, key, spectral analysis
- `pyloudnorm` — integrated loudness (LUFS, EBU R128)
- `ffmpeg` — required by librosa for MP3/AAC decoding

---

## Environment Setup

Create a `.env` file based on `.env.example`:
```
SPOTIPY_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SPOTIPY_CLIENT_SECRET=yyyyyyyyyyyyyyyyyyyyyyyyyyyy
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

Get credentials at: https://developer.spotify.com/dashboard

**Two auth modes:**
- **Client Credentials** (`--use-client-credentials`): No browser login, public data only
- **Authorization Code Flow** (default): Opens browser for user OAuth, enables private playlists

The `.cache` file (spotipy token cache) is git-ignored. Do not commit it.

---

## Script Reference

### `spotify_auth_test.py` — OAuth Validation
Quick check that credentials work. Run this first after setting up `.env`.
```bash
python spotify_auth_test.py
```

### `spotify_playlist_features.py` — Main Playlist Harvester
Fetches tracks and audio features from playlists across multiple markets.
```bash
# Fetch specific playlists for DE and US markets
python spotify_playlist_features.py --playlists 37i9dQZEVXbMDoHDwVN2tF --markets DE US

# Use market shortcuts, merge results
python spotify_playlist_features.py -all --merge

# Use client credentials (no browser popup)
python spotify_playlist_features.py -DE --use-client-credentials
```
**Key args**: `--playlists`, `--outdir`, `--markets DE US UK`, `--merge`, `-DE/-US/-UK/-all`, `--use-client-credentials`, `--no-menu`

### `example_playlist_pull.py` — Robust Single Playlist Puller
Production-ready with 403/429 recovery; falls back to single-track audio feature fetching.
```bash
python example_playlist_pull.py --playlist-id 37i9dQZEVXbMDoHDwVN2tF --market DE
python example_playlist_pull.py --playlist-name "Top 50 Germany" -U --out my_output.csv
```
**Key args**: `--playlist-id`, `--playlist-name`, `--market`, `-U` (user auth), `--out`, `--force`

### `spotify_audio_features_batch.py` — Batch Track Feature Extraction
Extract Spotify audio features from a CSV of track URLs/IDs or title+artist search terms.
```bash
python spotify_audio_features_batch.py --in input/input_spotify_tracks.csv --out output/features.csv
python spotify_audio_features_batch.py --search input/input_spotify_search.csv --out output/features.csv
```
**Key args**: `--in` (track column), `--search` (title/artist columns), `--out`

### `local_audio_features.py` — Local MIR Analysis
Analyze local WAV/MP3/FLAC files using librosa and pyloudnorm.
```bash
python local_audio_features.py --in local_audio/ --out output/local_features.csv
```
**Key args**: `--in` (directory), `--out`

**Extracted features**: `duration_sec`, `tempo_bpm`, `spectral_centroid_mean`, `rms_mean`, `energy_variance`, `lufs_i`, `key_est`, `samplerate`

### `build_genre_ref_stats.py` — Genre Reference Builder
Uses Spotify Recommendations API to build statistical reference clusters per genre/market.
```bash
python build_genre_ref_stats.py --markets DE US --genres pop rock metal house
```
**Key args**: `--markets`, `--genres`, `--outdir`
**Output**: `output/refdata/genre_{MARKET}_{GENRE}_stats.csv`

### `score_rank.py` — Z-Score Ranking Engine
Ranks local tracks against reference genre clusters using Z-score distance.
```bash
python score_rank.py \
  --local output/local_features.csv \
  --stats output/refdata/genre_DE_pop_stats.csv output/refdata/genre_DE_rock_stats.csv \
  --features tempo energy valence \
  --out output/ranking.csv
```
**Key args**: `--local`, `--stats` (one or more), `--features` (priority order), `--weights f=w`, `--out`

---

## Data Flows

### Workflow A: Spotify Playlist Analysis
```
Playlist IDs (playlist_ids.txt or CLI)
  → spotify_playlist_features.py / example_playlist_pull.py
  → Spotify API: /playlists/{id}/items + /audio-features
  → output/playlist_{name}_{market}.csv
```

### Workflow B: Reference Genre Cluster Building
```
Seed genres (CLI args)
  → build_genre_ref_stats.py
  → Spotify API: /recommendations + /audio-features
  → output/refdata/genre_{market}_{genre}_stats.csv
```

### Workflow C: Local Audio Scoring
```
Local audio files (WAV/MP3/FLAC)
  → local_audio_features.py  →  output/local_features.csv
  → score_rank.py  (vs. reference stats CSVs)
  → output/ranking.csv
```

---

## Data Schemas

### Input CSVs
| File | Columns | Notes |
|------|---------|-------|
| `input_spotify_search.csv` | `title, artist` | Used with `--search` flag |
| `input_spotify_tracks.csv` | `track` | Spotify URL or ID |
| `playlist_ids.txt` | one ID per line | `#` lines are comments |

### Spotify Audio Features (from API)
`danceability`, `energy`, `valence`, `tempo`, `loudness`, `key`, `mode`, `time_signature`, `speechiness`, `acousticness`, `instrumentalness`, `liveness`

### Local MIR Features (from librosa/pyloudnorm)
`duration_sec`, `tempo_bpm`, `spectral_centroid_mean`, `rms_mean`, `energy_variance`, `lufs_i`, `key_est`, `samplerate`

---

## Error Handling Conventions

All scripts follow a consistent error recovery pattern for Spotify API calls:

| HTTP Status | Cause | Strategy |
|-------------|-------|----------|
| `429` Too Many Requests | Rate limit | Exponential backoff, up to 5 retries |
| `403` Forbidden | Bulk audio-features blocked | Fall back to per-track single fetches |
| `404` Not Found | Playlist/track missing | Skip gracefully, log metric, continue |
| Other errors | Network/DNS/auth | Log and continue pipeline |

The helper `api_call_with_retries()` in `spotify_playlist_features.py` (lines 38–74) wraps all Spotify API calls. Replicate this pattern when adding new API calls.

---

## Code Conventions

- **Python 3.12** — use f-strings, `pathlib.Path`, `argparse`
- **No classes** — all scripts use module-level functions and a `main()` entry point guarded by `if __name__ == "__main__":`
- **pandas** for all data I/O (read_csv / to_csv), filtering, and aggregation
- **tqdm** for progress bars in any loop over API calls
- **dotenv** loaded at the top of every script that uses Spotify credentials
- **Output directory**: always `output/` relative to CWD, created with `pathlib.Path.mkdir(parents=True, exist_ok=True)`
- **No logging module** — scripts use `print()` for status messages
- **Line endings**: `.py` files use LF, `.ps1` files use CRLF (enforced by `.gitattributes`)

---

## Testing

pytest is installed but no test files exist yet. To add tests:
- Place test files in a `tests/` directory named `test_*.py`
- Run with `pytest` from the project root
- `spotify_auth_test.py` is a manual integration smoke test, not a pytest test

---

## Git-Ignored Paths

Do not commit the following (enforced by `.gitignore`):
- `.venv312/` — virtual environment
- `.env` — credentials
- `.cache` / `.cache/` — Spotipy OAuth token
- `output/` — generated CSVs (except `.gitkeep`)
- `local_audio/` — local audio files (except `.gitkeep`)
- `__pycache__/`, `*.pyc` — Python cache

---

## GitHub Actions

### `claude.yml`
Responds to `@claude` mentions in issues and PR comments using `anthropics/claude-code-action@v1`.

### `claude-code-review.yml`
Runs automated code review on every PR open/sync/reopen using the `code-review@claude-code-plugins` plugin.

Both workflows require `ANTHROPIC_API_KEY` set as a repository secret.

---

## Common Tasks for AI Assistants

### Adding a new script
1. Follow the existing pattern: `argparse` → `load_dotenv()` → helper functions → `main()` → `if __name__ == "__main__": main()`
2. Use `api_call_with_retries()` from `spotify_playlist_features.py` (or replicate the pattern) for any Spotify API calls
3. Write output CSVs to `output/` using `pathlib`
4. Add `tqdm` progress bars for loops over API calls

### Extending audio features
- Spotify features are fixed by the API schema
- For local MIR features, add new computations in `local_audio_features.py` and update the feature list in `score_rank.py`

### Debugging auth issues
1. Delete `.cache` to force re-auth
2. Run `python spotify_auth_test.py` to verify credentials
3. Check that `SPOTIPY_REDIRECT_URI` in `.env` matches the app settings in Spotify Dashboard
4. Use `--use-client-credentials` flag to bypass OAuth for public data

### Adding market support
Markets are ISO 3166-1 alpha-2 codes (e.g., `DE`, `US`, `GB`). Pass via `--markets` CLI arg. The Spotify API uses the `market` parameter for availability filtering.
