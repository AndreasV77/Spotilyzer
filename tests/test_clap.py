"""
Tests for CLAPAnalyzer and CLAPResult.

Unit tests (default): no model weights loaded, all ML objects mocked.
Integration tests (@pytest.mark.slow): require the real CLAP model and a test
audio file; skipped unless -m slow is passed to pytest.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from spotilyzer import CLAP_CHUNK_SEC
from spotilyzer.core.clap_analyzer import CLAPAnalyzer, DEFAULT_TAG_SETS
from spotilyzer.data.models import CLAPResult


# ── CLAPResult: serialization and properties ──────────────────────────────────

class TestCLAPResult:
    def test_roundtrip(self):
        cr = CLAPResult(
            tag_scores={"genre": {"metal": 0.42, "pop": 0.18}, "mood": {"dark": 0.35}},
            top_tags=["metal", "dark", "pop"],
        )
        assert CLAPResult.from_dict(cr.to_dict()).tag_scores == cr.tag_scores
        assert CLAPResult.from_dict(cr.to_dict()).top_tags == cr.top_tags

    def test_scores_rounded_to_4dp(self):
        cr = CLAPResult(tag_scores={"genre": {"metal": 0.123456789}}, top_tags=[])
        assert cr.to_dict()["tag_scores"]["genre"]["metal"] == 0.1235

    def test_genre_and_mood_properties(self):
        cr = CLAPResult(
            tag_scores={"genre": {"metal": 0.5}, "mood": {"dark": 0.3}},
            top_tags=[],
        )
        assert cr.genre_scores == {"metal": 0.5}
        assert cr.mood_scores == {"dark": 0.3}

    def test_top_genre_and_mood(self):
        cr = CLAPResult(
            tag_scores={
                "genre": {"metal": 0.5, "pop": 0.2},
                "mood": {"dark": 0.3, "upbeat": 0.1},
            },
            top_tags=[],
        )
        assert cr.top_genre() == "metal"
        assert cr.top_mood() == "dark"

    def test_top_genre_empty_returns_none(self):
        assert CLAPResult(tag_scores={}, top_tags=[]).top_genre() is None
        assert CLAPResult(tag_scores={}, top_tags=[]).top_mood() is None

    def test_from_dict_empty(self):
        cr = CLAPResult.from_dict({})
        assert cr.tag_scores == {}
        assert cr.top_tags == []


# ── CLAPAnalyzer: audio loading ───────────────────────────────────────────────

class TestAudioLoading:
    def test_resamples_44100_to_48000(self, mock_clap, wav_44100):
        path, _ = wav_44100
        waveform, sr = mock_clap._load_audio(path)
        assert sr == CLAPAnalyzer.CLAP_SAMPLE_RATE
        assert waveform.ndim == 1

    def test_48000_unchanged(self, mock_clap, wav_48000):
        path, _ = wav_48000
        _, sr = mock_clap._load_audio(path)
        assert sr == CLAPAnalyzer.CLAP_SAMPLE_RATE

    def test_stereo_converted_to_mono(self, mock_clap, wav_stereo_44100):
        path, _ = wav_stereo_44100
        waveform, _ = mock_clap._load_audio(path)
        assert waveform.ndim == 1

    def test_resampled_length_within_tolerance(self, mock_clap, wav_44100):
        # 5 s at 44 100 Hz → 5 s at 48 000 Hz = 240 000 samples ± 10 ms
        path, _ = wav_44100
        waveform, _ = mock_clap._load_audio(path)
        assert abs(len(waveform) - 5 * 48_000) < 480


# ── CLAPAnalyzer: waveform chunking ──────────────────────────────────────────

class TestWaveformChunking:
    def test_long_track_split_correctly(self, mock_clap):
        # 35 s → three full 10 s chunks + one 5 s tail (5 s > 3 s minimum)
        sr = 48_000
        waveform = np.zeros(sr * 35, dtype=np.float32)
        chunks = mock_clap._chunk_waveform(waveform, sr)
        assert len(chunks) == 4

    def test_exact_multiple_no_tail(self, mock_clap):
        # 20 s = exactly 2 × 10 s chunks, no tail
        sr = 48_000
        waveform = np.zeros(sr * 20, dtype=np.float32)
        chunks = mock_clap._chunk_waveform(waveform, sr)
        assert len(chunks) == 2

    def test_tail_under_3s_discarded(self, mock_clap):
        # 12 s → one full 10 s chunk + 2 s tail (2 s < 3 s minimum → discarded)
        sr = 48_000
        waveform = np.zeros(sr * 12, dtype=np.float32)
        chunks = mock_clap._chunk_waveform(waveform, sr)
        assert len(chunks) == 1

    def test_very_short_track_fallback(self, mock_clap):
        # 2 s < 3 s minimum → chunks list empty → fallback returns one chunk
        sr = 48_000
        waveform = np.zeros(sr * 2, dtype=np.float32)
        chunks = mock_clap._chunk_waveform(waveform, sr)
        assert len(chunks) == 1

    def test_chunk_max_length(self, mock_clap):
        sr = 48_000
        waveform = np.zeros(sr * 55, dtype=np.float32)
        for chunk in mock_clap._chunk_waveform(waveform, sr):
            assert len(chunk) <= CLAP_CHUNK_SEC * sr


# ── CLAPAnalyzer: score calculation and aggregation ───────────────────────────

class TestScoreCalculation:
    def test_top_tags_sorted_descending(self, mock_clap):
        """Tags with the highest scores appear first in top_tags."""
        tags = ["metal", "pop", "classical", "jazz", "rock"]
        # metal(0.8) > jazz(0.5) > pop(0.3) > rock(0.2) > classical(0.1)
        scores = np.array([0.8, 0.3, 0.1, 0.5, 0.2])
        waveform = np.zeros(48_000 * 5, dtype=np.float32)

        with patch.object(mock_clap, "_get_scores_for_tags", return_value=scores), \
             patch.object(mock_clap, "_load_audio", return_value=(waveform, 48_000)):
            result = mock_clap.analyze(Path("dummy.wav"), tag_sets={"genre": tags})

        assert result.top_tags[0] == "metal"
        assert result.top_tags[1] == "jazz"
        assert result.top_tags[-1] == "classical"

    def test_scores_averaged_across_chunks(self, mock_clap):
        """
        Each chunk is scored independently; the final score is the mean.

        Two chunks with different scores:
            Chunk 1 → metal: 0.8, pop: 0.2
            Chunk 2 → metal: 0.4, pop: 0.6
        Expected mean → metal: 0.6, pop: 0.4

        This mirrors the training data format: each 10 s segment is scored
        independently, then averaged — so a song with a quiet intro and a loud
        chorus doesn't get dominated by either section alone.
        """
        tags = ["metal", "pop"]
        chunk_scores_seq = [np.array([0.8, 0.2]), np.array([0.4, 0.6])]
        call_count = {"n": 0}

        def score_side_effect(wf, sr, t):
            s = chunk_scores_seq[call_count["n"]]
            call_count["n"] += 1
            return s

        # 20 s → exactly 2 × 10 s chunks (no tail)
        waveform = np.zeros(48_000 * 20, dtype=np.float32)

        with patch.object(mock_clap, "_get_scores_for_tags", side_effect=score_side_effect), \
             patch.object(mock_clap, "_load_audio", return_value=(waveform, 48_000)):
            result = mock_clap.analyze(Path("dummy.wav"), tag_sets={"genre": tags})

        assert abs(result.genre_scores["metal"] - 0.6) < 1e-5
        assert abs(result.genre_scores["pop"]   - 0.4) < 1e-5

    def test_empty_tag_set_skipped(self, mock_clap):
        """A tag set with no tags is silently skipped."""
        waveform = np.zeros(48_000 * 5, dtype=np.float32)
        with patch.object(mock_clap, "_load_audio", return_value=(waveform, 48_000)):
            result = mock_clap.analyze(
                Path("dummy.wav"),
                tag_sets={"genre": [], "mood": ["dark", "bright"]},
            )
        assert "genre" not in result.tag_scores
        assert "mood" in result.tag_scores

    def test_default_tag_sets_used_when_none(self, mock_clap):
        """Passing tag_sets=None falls back to DEFAULT_TAG_SETS."""
        waveform = np.zeros(48_000 * 5, dtype=np.float32)

        def zero_scores(wf, sr, tags):
            return np.zeros(len(tags))

        with patch.object(mock_clap, "_get_scores_for_tags", side_effect=zero_scores), \
             patch.object(mock_clap, "_load_audio", return_value=(waveform, 48_000)):
            result = mock_clap.analyze(Path("dummy.wav"), tag_sets=None)

        assert len(result.genre_scores) == len(DEFAULT_TAG_SETS["genre"])
        assert len(result.mood_scores)  == len(DEFAULT_TAG_SETS["mood"])

    def test_result_has_correct_top_n_tags(self, mock_clap):
        """top_tags contains exactly TOP_N_TAGS entries (or fewer if fewer tags exist)."""
        from spotilyzer.core.clap_analyzer import TOP_N_TAGS
        tags = ["a", "b", "c", "d", "e", "f", "g"]
        waveform = np.zeros(48_000 * 5, dtype=np.float32)
        scores = np.arange(len(tags), dtype=np.float32)  # ascending → "g" is highest

        with patch.object(mock_clap, "_get_scores_for_tags", return_value=scores), \
             patch.object(mock_clap, "_load_audio", return_value=(waveform, 48_000)):
            result = mock_clap.analyze(Path("dummy.wav"), tag_sets={"genre": tags})

        assert len(result.top_tags) == TOP_N_TAGS
        assert result.top_tags[0] == "g"  # highest score


# ── Integration: real CLAP inference (opt-in, slow) ──────────────────────────

_REAL_AUDIO = Path(__file__).parent.parent / "Train - 01 - Save Me, San Francisco.flac"


@pytest.mark.slow
@pytest.mark.skipif(not _REAL_AUDIO.exists(), reason="test audio file not present")
class TestCLAPIntegration:
    def test_analyze_returns_valid_result(self):
        analyzer = CLAPAnalyzer.get_instance(device="cpu")
        result = analyzer.analyze(_REAL_AUDIO)

        assert isinstance(result, CLAPResult)
        assert "genre" in result.tag_scores
        assert "mood" in result.tag_scores
        assert len(result.top_tags) == 5
        for scores in result.tag_scores.values():
            for score in scores.values():
                assert isinstance(score, float)

    def test_top_genre_is_string(self):
        analyzer = CLAPAnalyzer.get_instance(device="cpu")
        result = analyzer.analyze(_REAL_AUDIO)
        assert isinstance(result.top_genre(), str)
        assert isinstance(result.top_mood(), str)
