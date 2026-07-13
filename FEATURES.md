# Spotilyzer — Feature Overview

ML-based audio analysis tool for music. Two goals, in this order:

1. **Neutral song analysis** — technical and musical data for sound reproducibility, strengths/weaknesses profiling
2. **Hit potential assessment** — Hit / Mid / Flop classification as a decision aid

Pipeline: `audio → MERT-v1-330M (1024-dim) → XGBoost → rating + spectral/diagnostic layer + optional CLAP tags`

---

## Status Overview

Legend: ✅ implemented · 🔶 in progress / blocked · ⚪ planned

| Area | Feature | Status | Technology |
|---|---|---|---|
| **Basic metadata** | Duration, sample rate, channels, bitrate, format, file size | ✅ | torchaudio, pathlib |
| **Audio metrics** | BPM (beat tracker + octave correction) | ✅ | librosa DP beat tracker |
| | LUFS (integrated, EBU R128) | ✅ | pyloudnorm |
| | LRA (loudness range) | ✅ | pyloudnorm |
| | True peak (inter-sample) | ✅ | scipy 4× oversampling |
| | Key + scale | ✅ | librosa chroma_cqt + chroma_cens |
| | Spectral centroid, flatness, onset rate | ✅ | librosa |
| **Hit prediction** | Rating (Hit/Mid/Flop) + confidence + probabilities | ✅ | MERT-v1-330M + XGBoost |
| **Spectral layer** *(`analysis/`)* | Spectral: centroid, bandwidth, rolloff, flatness, contrast, tilt, 4-band energy | ✅ | librosa |
| | Temporal: tempo stability, onset rate, beat strength, HPSS ratio | ✅ | librosa |
| | Production: stereo width, mid/side, dynamic range, crest factor, clipping ratio | ✅ | numpy + scipy |
| | Normalization with category thresholds + AI context generator | ✅ | custom implementation |
| **Diagnostic layer** *(`analysis/`)* | 7-band mix diagnostics: boominess, muddiness, boxiness, harshness, presence, air, sparkle | ✅ | librosa |
| | Role prominence (kick, bass, vocals, percussion, harmonic) | ✅ | HPSS + frequency-band analysis |
| **Semantic layer** | Zero-shot genre/mood tags | ✅ | LAION CLAP (`laion/clap-htsat-fused`) |
| | Configurable tag sets (genre, mood, production style) | ✅ | DEFAULT_TAG_SETS + override |
| **GUI / CLI** | PySide6 GUI with three view modes (Simple/Balanced/Pro) | ✅ | PySide6 |
| | CLI with JSON / CSV / Markdown / TXT export | ✅ | argparse + custom exporters |
| | Audio preview + waveform visualization | ✅ | QtMultimedia |
| | Auto-save / persistence across sessions | ✅ | JSON v2.0 schema |
| **Phase 3 (planned)** | Essentia (key, danceability, rhythm) | 🔶 | stub present, Windows build blocked |
| | ACE-Step LM Planner (BPM, key, time signature, caption) | ⚪ | CoT module isolation open |
| | Time signature detection | ⚪ | librosa beat tracking + pattern |
| | Reference delta (genre medians, track comparison) | ⚪ | custom genre statistics |
| | Arrangement analysis (section segmentation) | ⚪ | novelty-curve based |
| | Stem separation (vocals, drums, bass, other) | ⚪ | Demucs |
| | Genre classifier (second model) | ⚪ | XGBoost on MERT |
| | "Sounds like…" similarity search | ⚪ | MERT embedding space |
| | Portable Windows EXE | ⚪ | PyInstaller + CUDA strip |

---

## Implemented Features in Detail

### Basic metadata

Standard audio properties: duration, sample rate, channel count, bitrate, format detection, file size. Trivial but complete. Supported formats: `.mp3`, `.flac`, `.wav`, `.ogg`, `.m4a`, `.aac`, `.wma`.

### Audio metrics (EBU R128 + librosa)

- **BPM** via librosa dynamic-programming beat tracker with downstream octave correction (halving/doubling heuristic)
- **LUFS** integrated per EBU R128 (K-weighting, 400 ms block gating) via `pyloudnorm`
- **Loudness range (LRA)** and **true peak** also EBU R128 compliant; true peak with 4× oversampling, detects inter-sample clipping
- **Key detection** combines `chroma_cqt` and `chroma_cens` with Krumhansl-Schmuckler profiles
- **Spectral centroid / flatness / onset rate** replace the older "energy" metric with clearly defined, separate quantities

### Hit prediction

Three-class classification on MERT embeddings (1024 dimensions, model `m-a-p/MERT-v1-330M`) with XGBoost. Trained on 24,170 validated samples from Deezer charts, Spotify Top 200 and Kworb history across 12 markets (refreshed 2026-07-13).

Current performance on holdout (4,834 samples):

| Metric | Value |
|---|---|
| Balanced accuracy | 64.3 % |
| Hit recall | 82.4 % |
| Flop recall | 74.5 % |
| Mid recall | 36.0 % |

Mid remains difficult (frequently confused with Hit). The audio-only ceiling without metadata and without artist-deduplicated training sits around 64–65 % BA.

Inference ~0.8 s/track on a GTX 1660 Ti.

### Spectral & diagnostic layer (`spotilyzer/analysis/`)

Three-tier architecture that complements MERT embeddings with interpretable features:

- **Tier 1: Raw data** — MERT 1024-dim, optional CLAP 512-dim, mel spectrogram
- **Tier 2A: Interpretable measurements** — the spectral, temporal and production features listed in the table, each with raw value + normalization + semantic category (`very_low` … `very_high`)
- **Tier 2B: Diagnostic abstractions** — 7-band mix diagnostics (e.g. shows muddiness in the 200–500 Hz range) and role prominence (kick / bass / vocals / percussion / harmonic) without stem separation, based on HPSS and frequency-band analysis

`FeatureExtractor` orchestrates everything. The `to_ki_context()` method produces a natural-language context string for LLM prompts ("mix tends toward elevated muddiness in the 200–500 Hz range, vocal presence above average").

### Semantic layer (CLAP)

LAION CLAP (`laion/clap-htsat-fused`; general-purpose — `laion/larger_clap_music` was dropped 2026-07-13, its HF conversion is defective, see CLAUDE.md) for zero-shot audio-text alignment. Arbitrary tag lists comparable:

```python
clap.analyze(audio, tag_sets={
    "genre": ["aggressive metal", "indie pop", "techno", ...],
    "mood":  ["aggressive", "melancholic", "euphoric", ...],
})
```

Result: similarity scores per tag, no training required. Tag sets are swappable via configuration. CLAP is loaded on demand (`--include-clap`), not at startup.

### GUI / CLI

PySide6 GUI with three complexity tiers:

- **Simple** — drop zone, rating display, nothing else
- **Balanced** — highscore, history and tech panels visible
- **Pro** — all dock panels including file browser and settings

The CLI covers the same pipeline, with optional flags `--include-clap`, `--vram-mode`, `--full-analysis`, `--threesome` (batch table for BPM/LUFS/TruePeak/PLR/Key across folders). Export to JSON, CSV, Markdown, TXT.

All ML work runs in QThread workers; the UI stays responsive.

---

## In Progress / Planned

### 🔶 Essentia integration

Stub module exists (`essentia_features.py` for key, danceability, rhythm). Blocked: no PyPI wheel for Windows; native compilation requires MSVC + CMake + Eigen3 + libav via vcpkg. Will be re-evaluated once a stable Windows build becomes available. Not suitable for a portable EXE (native C++ dependencies).

### ⚪ ACE-Step LM Planner

The chain-of-thought component of the ACE-Step model returns BPM, key, time signature, language and caption in a single call. Open question: can this component be loaded in isolation, without the full DiT generator? If so, it replaces several planned individual features (time signature, more accurate key detection, automatic captioning).

### ⚪ Reference delta engine

Z-scores and genre-median deviations, based on genre statistics derived from the project's own training dataset. Produces statements like *"centroid sits 1.4 σ above the median for indie rock"*. Prerequisite: aggregate genre statistics (mean, std, median per feature per genre).

### ⚪ Arrangement features

Section segmentation via novelty curve, yielding energy trajectory (flat / building / declining), climax position, section contrast. Foundation for future improvement suggestions ("chorus could carry more energy than the verse").

### ⚪ Stem-based analysis

Demucs integration on demand (~3 GB model, ~5–10 s per track on GPU). Separate embeddings and spectral features per stem (vocals, drums, bass, other). Open research question: does this improve hit prediction, or is the full mix sufficient?

### ⚪ Other planned features

- **Time signature detection** — beat tracking + pattern analysis, standalone or via ACE-Step
- **Genre classifier** — second model for cluster assignment, parallel to the rating
- **"Sounds like…"** — similarity search in MERT embedding space, local library vs. track
- **Genre-specific models** — one classifier per cluster (long-term)
- **Portable Windows EXE** — PyInstaller + CUDA strip, target size ~3 GB
- **Reproduction of legacy Spotify metrics** — valence, danceability, acousticness, instrumentalness, speechiness, liveness as ML classifiers on MERT (open, not prioritized)

---

## Known Limitations

- **BPM metric level** — the beat tracker locks onto the quarter-note pulse. In genres with a strong half-time feel (typical in metal, trap, several electronic styles), the reported BPM corresponds to the "groove pulse" rather than the perceived tempo level. A genre-aware heuristic would be required and is not yet implemented.
- **CLAP on metal subgenres** — `laion/clap-htsat-fused` (general-purpose, not music-specialized) does not reliably distinguish gothic / doom / black / death metal, and shows an unexplained bias toward "hip-hop" scoring high regardless of genre. Adding specific subgenre tags to the tag list helps marginally. Recovering a music-specialized model via the original `laion_clap` checkpoint is planned.
- **Mid class recall** — 36.0 %. Mid tracks are frequently classified as Hit. Below ~60 % confidence, results should be treated as uncertain.
- **Audio-only BA ceiling** — ~64–65 %. Improvements require artist-level deduplication (GroupKFold) during training or additional metadata features.

---

## Tech Stack

- **DSP foundation:** librosa, numpy, scipy, pyloudnorm
- **ML:** PyTorch, transformers (Hugging Face), XGBoost, scikit-learn
- **Audio models:** MERT-v1-330M (embeddings), LAION CLAP (zero-shot)
- **GUI:** PySide6, QtMultimedia
- **Code license:** [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — free for non-commercial use. Commercial use requires a separate agreement with the author.
- **Model licenses:** MERT (CC-BY-NC), CLAP (Apache 2.0)

## Hardware Profile

- **Single-user desktop tool**, typical batch size 1–10 tracks per session
- **Latency tolerance:** a few seconds per track is acceptable
- **Inference:** GPU recommended, CPU fallback works (slower)
- **VRAM:** 6 GB sufficient (sequential loading of MERT and CLAP); 8+ GB allows parallel loading

---
