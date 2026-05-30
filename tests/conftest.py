"""
Shared pytest fixtures for Spotilyzer tests.
"""

import numpy as np
import pytest
import torch
from unittest.mock import MagicMock, patch

from spotilyzer.core.clap_analyzer import CLAPAnalyzer


@pytest.fixture(autouse=True)
def reset_clap_singleton():
    """Reset the CLAPAnalyzer singleton before and after every test."""
    CLAPAnalyzer.reset_instance()
    yield
    CLAPAnalyzer.reset_instance()


@pytest.fixture
def mock_clap():
    """
    CLAPAnalyzer instance with mocked model and processor.

    No model weights are downloaded; all heavy ML objects are replaced with
    MagicMocks so the Python logic (audio loading, chunking, aggregation) can
    be tested in isolation.
    """
    mock_model = MagicMock()
    # _ensure_on_device calls next(self.model.parameters()).device — return
    # a fake tensor so str(device) comparison works without crashing.
    fake_param = torch.zeros(1)
    mock_model.parameters.return_value = iter([fake_param])

    with patch("spotilyzer.core.clap_analyzer.ClapModel.from_pretrained", return_value=mock_model), \
         patch("spotilyzer.core.clap_analyzer.ClapProcessor.from_pretrained", return_value=MagicMock()):
        analyzer = CLAPAnalyzer(device="cpu")

    yield analyzer


@pytest.fixture
def wav_44100(tmp_path):
    """Silence WAV at 44 100 Hz — standard non-CLAP sample rate."""
    import soundfile as sf
    sr, duration = 44_100, 5
    path = tmp_path / "silence_44100.wav"
    sf.write(str(path), np.zeros(sr * duration, dtype=np.float32), sr)
    return path, sr


@pytest.fixture
def wav_48000(tmp_path):
    """Silence WAV at 48 000 Hz — CLAP native sample rate."""
    import soundfile as sf
    sr, duration = 48_000, 5
    path = tmp_path / "silence_48000.wav"
    sf.write(str(path), np.zeros(sr * duration, dtype=np.float32), sr)
    return path, sr


@pytest.fixture
def wav_stereo_44100(tmp_path):
    """Stereo silence WAV at 44 100 Hz."""
    import soundfile as sf
    sr, duration = 44_100, 3
    path = tmp_path / "stereo_44100.wav"
    sf.write(str(path), np.zeros((sr * duration, 2), dtype=np.float32), sr)
    return path, sr
