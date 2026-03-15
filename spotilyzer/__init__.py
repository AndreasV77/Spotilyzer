"""
Spotilyzer - Hit/Mid/Flop Audio Analyzer
=========================================
ML-basierte Bewertung der Mainstream-Kompatibilität von Audio-Tracks.
Pipeline: MERT-v1-330M Embeddings → XGBoost 3-Klassen-Klassifikation.

Autor: Claude Opus (für Andreas Vogelsang)
"""

__version__ = "2.0.0"
__author__ = "Andreas Vogelsang"

# Unterstützte Audio-Formate
SUPPORTED_FORMATS = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".wma"}

# MERT-Konfiguration
MERT_MODEL_NAME = "m-a-p/MERT-v1-330M"
MERT_EMBEDDING_DIM = 1024          # 95M → 768, 330M → 1024
TARGET_SAMPLE_RATE = 24000
MAX_AUDIO_LENGTH_SEC = 30

# CLAP-Konfiguration
CLAP_MODEL_NAME = "laion/clap-htsat-fused"
