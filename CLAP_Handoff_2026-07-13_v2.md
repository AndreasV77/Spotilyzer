# Handoff v2: CLAP integration produces meaningless genre/mood scores

**Project:** Spotilyzer (`G:\dev\source\Spotilyzer`)
**Date:** 2026-07-13 (v2 — supersedes `CLAP_Handoff_2026-07-13.md`)
**Status:** Root cause identified and externally verified. Fix decision made (two-stage plan below), NOT yet applied.
**Changes vs. v1:** Section 4 root cause corrected (HF conversion defect, not degenerate trained weights); Section 5 replaced by a two-stage recommendation; Section 6 questions answered with sources; new Section 7 (architecture link to Stufe 2 confidence scoring).

---

## 1. Original observation (unchanged)

Export `spotilyzer_export_2026-07-13.json` (21 tracks: AI-generated metal, Jack Johnson, Olivia Rodrigo, Train, Lorde, etc.): **all tracks receive nearly identical CLAP `top_tags`** — consistently `["romantic", "indie", "dreamy", "dance", "tense"]` with score deltas of 0.001–0.01. Metal tags barely surface even on unambiguous metal tracks.

## 2. Affected component (unchanged)

- `spotilyzer/core/clap_analyzer.py`
- `CLAP_MODEL_NAME = "laion/larger_clap_music"` (`spotilyzer/__init__.py:25`)
- `transformers==5.3.0` in `.venv-spotilyzer`

## 3. Investigation findings (unchanged, summary)

- Spotilyzer code (chunking, 48 kHz resampling, mean pooling) is correct; bug reproduces with a single unchunked 10 s excerpt.
- `model.logit_scale_a.exp()` ≈ 1.03 (healthy: ~20–100).
- Text encoder collapse: cosine similarity between embeddings of arbitrary, unrelated text inputs is 0.998–0.999, stable across all 12 layers.
- Prompt templates and mean-centering do not help.
- Control experiment: `laion/clap-htsat-fused`, identical code and transformers version → healthy (`logit_scale_a.exp()` ≈ 27.8, text similarities −0.13 to +0.28).

## 4. Root cause (CORRECTED in v2)

**v1 claim:** "The published model weights themselves are defective/degenerate."
**Corrected claim:** The **HuggingFace conversion** of a healthy model is defective. The underlying trained model works.

Evidence:

1. **LAION-AI/CLAP GitHub Issue #126** ("Acc drop after converting HTSAT-base type to huggingface model") documents, for exactly this checkpoint family, a measured collapse after conversion to HF format: zero-shot R@1 drops from **0.9175 (original .pt) to 0.4700 (HF-converted)** for `music_audioset_epoch_15_esc_90.14`. Never resolved.
   → https://github.com/LAION-AI/CLAP/issues/126
2. The original checkpoint `music_audioset_epoch_15_esc_90.14.pt` (the model behind `larger_clap_music`) has published, reproduced benchmark numbers via the `laion_clap` pip package: **90.14% zero-shot ESC50, 71% zero-shot GTZAN** (prompt: "This audio is a <genre> song."). A model with a collapsed text encoder cannot score 71% on 10-way genre classification.
   → https://github.com/LAION-AI/CLAP (README, checkpoint list)
3. **HF discussion `laion/larger_clap_music/discussions/2`** (Xenova, Dec 2023): same symptom, four confirmations over two years, no response from LAION. Consistent with a conversion artifact nobody fixed on the Hub.
   → https://huggingface.co/laion/larger_clap_music/discussions/2

Consequence unchanged for our code: the HF checkpoint `laion/larger_clap_music` is unusable and will not be fixed by anything in Spotilyzer. New consequence: **the music-specialized model itself is recoverable** via the original checkpoint.

## 5. Recommendation (REVISED in v2): two-stage plan

### Stage 1 — immediate unblock (this session)

Switch `CLAP_MODEL_NAME` in `spotilyzer/__init__.py:25` from `laion/larger_clap_music` to `laion/clap-htsat-fused`.

- Already cached locally, verified healthy with identical code (Section 3).
- General-purpose, not music-specialized; known weakness on metal subgenre discrimination is accepted for now.
- No other code changes required.

Do NOT switch to `laion/larger_clap_general` or `laion/larger_clap_music_and_speech`: same HF conversion lineage as the broken checkpoint; Issue #126 shows the conversion damage affects HTSAT-base conversions generally. (Corroborating datapoint: in Li et al., ICML 2026, `larger_clap_general` is by far the weakest LAION variant tested.)

### Stage 2 — recover the music-specialized model (separate session)

Add a second CLAP backend using the **original, unconverted** checkpoint via the official `laion_clap` pip package:

```python
import laion_clap

model = laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-base")
model.load_ckpt("path/to/music_audioset_epoch_15_esc_90.14.pt")
```

- Checkpoint source: LAION CLAP GitHub releases; mirrored on HF at `lukewys/laion_clap` (`music_audioset_epoch_15_esc_90.14.pt`, ~2.3 GB).
- This is the same model `larger_clap_music` was supposed to be, without the conversion defect. License Apache 2.0.
- Cost: extra dependency (`laion-clap`), separate API (not `transformers`), 48 kHz mono float32 input as before.
- Design: implement behind the existing analyzer interface (e.g. `CLAPBackend` abstraction: `hf` | `laion_clap`), configurable, both loadable. Respect `--low-vram` policy (sequential loading); both models individually fit in 8 GB.

### Stage 2 acceptance test

Benchmark both backends on the repo test files (`OverKill - 04 - Thanx For Nothin'.mp3` = thrash metal, `Train - 01 - Save Me, San Francisco.flac` = pop rock) plus a handful of own tracks with known ground truth:

- Sanity: "metal" > "romantic" and "aggressive" > "calm" for the OverKill track, inverse pattern for Train.
- Discrimination: top-5 tags must differ between the two tracks.
- Metal subgenre check (gothic/doom/black/death) on own AI-generated metal tracks — this is where the music checkpoint should justify its existence over `clap-htsat-fused`.

If the `laion_clap` music backend passes, it becomes the primary tag scorer.

## 6. Handoff questions — answered

1. **Is the collapse known/documented/explained?** Yes. HF discussion #2 (symptom, unfixed since Dec 2023) and LAION GitHub Issue #126 (mechanism: accuracy collapse after HF conversion of HTSAT-base checkpoints, with before/after numbers). Root cause is the conversion, not the training run.
2. **Recommended fix/workaround?** No fix for the HF checkpoint exists or is in sight. Workaround: use the original `.pt` checkpoint via `laion_clap` (Stage 2), or a verified-healthy HF checkpoint (`clap-htsat-fused`, Stage 1). Re-calibrating `logit_scale` cannot help — the text encoder output carries no input-specific information in the converted model.
3. **Better music-specialized alternative?** The best music-specialized option is the original model itself: `music_audioset_epoch_15_esc_90.14.pt` via `laion_clap` (GTZAN 71% zero-shot). No need to hunt for third-party alternatives first.

## 7. Architecture link: two backends → Stufe 2 confidence scoring

Li et al., "Stacking Complementary CLAP Embeddings" (ICML 2026), shows that different CLAP variants make **complementary** errors and that cross-model agreement is a stronger reliability signal than any single model. Their supervised stacking regressor is not transferable (requires human-labeled correspondence scores), but the cheap variant is:

- Run tag scoring on both backends (`clap-htsat-fused` + `laion_clap` music).
- **Agreement → high confidence** for the tag score; **disagreement → emit "unbestimmt" / low confidence.**

This directly implements the Stufe-2 design principle "prefer 'unbestimmt' with low confidence over guessing" for instrument/vocal/genre presence tags. The dual-backend setup from Stage 2 is therefore not throwaway evaluation scaffolding but the intended Stufe-2 architecture.

## 8. Reference files/paths

- `spotilyzer/core/clap_analyzer.py` — CLAP analyzer implementation
- `spotilyzer/__init__.py:25` — `CLAP_MODEL_NAME` constant
- `CLAUDE.md` — sections "CLAP genre accuracy on niche genres" (Known Issues) and "NEXT TASK: LAION CLAP Integration" — **update both after Stage 1**
- Test files in repo root: `OverKill - 04 - Thanx For Nothin'.mp3`, `Train - 01 - Save Me, San Francisco.flac`
- External references:
  - https://github.com/LAION-AI/CLAP/issues/126
  - https://huggingface.co/laion/larger_clap_music/discussions/2
  - https://github.com/LAION-AI/CLAP (checkpoint list + `laion_clap` usage)
  - https://huggingface.co/lukewys/laion_clap (checkpoint mirror)
