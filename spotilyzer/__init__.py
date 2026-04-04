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
MERT_CHUNK_SEC = 30                # Chunk-Größe für MERT-Inferenz; Volltracks werden in
                                   # 30s-Segmente aufgeteilt und deren Embeddings gemittelt.
                                   # (MERT-Transformer: O(n²) Attention → kein Full-Track-Modus)

# CLAP-Konfiguration
CLAP_MODEL_NAME = "laion/larger_clap_music"
CLAP_CHUNK_SEC = 10                # Natives CLAP-Fenster (ClapProcessor trunciert auf 10s);
                                   # Volltracks werden in 10s-Segmente aufgeteilt.
