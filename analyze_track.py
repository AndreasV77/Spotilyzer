"""
analyze_track.py
================
Analysiert einen lokalen Audio-Track und gibt eine Hit/Mid/Flop-Bewertung.

Workflow:
1. Audio laden und MERT-Embedding extrahieren
2. Embedding durch trainiertes XGBoost-Modell schicken
3. Ergebnis formatiert ausgeben

Input: Audio-Datei (MP3, WAV, FLAC, etc.)
Output: Bewertung mit Konfidenz

Autor: Claude Opus (für Andreas Vogelsang)
Datum: 2026-03-02
"""

import sys
import json
import argparse
from pathlib import Path

import numpy as np
import torch
import torchaudio
import joblib
from transformers import AutoModel, AutoProcessor

# ══════════════════════════════════════════════════════════════════════════════
# KONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_MODEL_PATH = "models/spotilyzer_model.joblib"
MERT_MODEL = "m-a-p/MERT-v1-95M"
TARGET_SAMPLE_RATE = 24000
MAX_AUDIO_LENGTH_SEC = 30


# ══════════════════════════════════════════════════════════════════════════════
# MERT-EMBEDDING
# ══════════════════════════════════════════════════════════════════════════════

class MERTEmbedder:
    """MERT-Embedding-Extraktor (Singleton-artig für Wiederverwendung)."""
    
    _instance = None
    
    def __init__(self, device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = AutoProcessor.from_pretrained(MERT_MODEL, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(MERT_MODEL, trust_remote_code=True)
        self.model.to(self.device)
        self.model.eval()
    
    @classmethod
    def get_instance(cls, device: str = None):
        if cls._instance is None:
            cls._instance = cls(device)
        return cls._instance
    
    def load_audio(self, filepath: Path) -> torch.Tensor | None:
        """Lädt und preprocessed Audio."""
        try:
            waveform, sample_rate = torchaudio.load(filepath)
            
            # Mono
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
            
            # Resample
            if sample_rate != TARGET_SAMPLE_RATE:
                resampler = torchaudio.transforms.Resample(sample_rate, TARGET_SAMPLE_RATE)
                waveform = resampler(waveform)
            
            # Max length
            max_samples = TARGET_SAMPLE_RATE * MAX_AUDIO_LENGTH_SEC
            if waveform.shape[1] > max_samples:
                # Nimm die Mitte des Tracks (interessantester Teil)
                start = (waveform.shape[1] - max_samples) // 2
                waveform = waveform[:, start:start + max_samples]
            
            return waveform.squeeze(0)
        except Exception as e:
            print(f"Fehler beim Laden: {e}", file=sys.stderr)
            return None
    
    @torch.no_grad()
    def extract_embedding(self, waveform: torch.Tensor) -> np.ndarray | None:
        """Extrahiert 768-dim Embedding."""
        try:
            inputs = self.processor(
                waveform.numpy(),
                sampling_rate=TARGET_SAMPLE_RATE,
                return_tensors="pt"
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            outputs = self.model(**inputs, output_hidden_states=True)
            embedding = outputs.last_hidden_state.mean(dim=1).squeeze(0)
            
            return embedding.cpu().numpy()
        except Exception as e:
            print(f"Fehler bei Embedding-Extraktion: {e}", file=sys.stderr)
            return None
    
    def process_file(self, filepath: Path) -> np.ndarray | None:
        """Komplette Pipeline: Laden → Embedding."""
        waveform = self.load_audio(filepath)
        if waveform is None:
            return None
        return self.extract_embedding(waveform)


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSE
# ══════════════════════════════════════════════════════════════════════════════

def analyze_track(
    filepath: Path,
    model_data: dict,
    embedder: MERTEmbedder,
    verbose: bool = True
) -> dict:
    """
    Analysiert einen Track und gibt Bewertung zurück.
    
    Returns:
        {
            "file": str,
            "rating": "hit" | "mid" | "flop",
            "confidence": float (0-1),
            "probabilities": {"hit": float, "mid": float, "flop": float}
        }
    """
    model = model_data["model"]
    label_encoder = model_data["label_encoder"]
    
    # Embedding extrahieren
    if verbose:
        print(f"  Extrahiere Embedding...", end=" ", flush=True)
    
    embedding = embedder.process_file(filepath)
    
    if embedding is None:
        return {"error": "Embedding-Extraktion fehlgeschlagen"}
    
    if verbose:
        print("OK")
    
    # Prediction
    embedding_2d = embedding.reshape(1, -1)
    proba = model.predict_proba(embedding_2d)[0]
    pred_idx = np.argmax(proba)
    pred_label = label_encoder.inverse_transform([pred_idx])[0]
    confidence = proba[pred_idx]
    
    # Probabilities als Dict
    prob_dict = {
        label: float(proba[i]) 
        for i, label in enumerate(label_encoder.classes_)
    }
    
    return {
        "file": filepath.name,
        "rating": pred_label,
        "confidence": float(confidence),
        "probabilities": prob_dict
    }


def print_result(result: dict, style: str = "default"):
    """Gibt das Analyse-Ergebnis formatiert aus."""
    
    if "error" in result:
        print(f"\n  ❌ Fehler: {result['error']}")
        return
    
    rating = result["rating"].upper()
    conf = result["confidence"]
    probs = result["probabilities"]
    
    # Rating-Emoji
    emoji = {"HIT": "🔥", "MID": "➖", "FLOP": "💀"}.get(rating, "?")
    
    # Konfidenz-Balken
    bar_len = 20
    filled = int(conf * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    
    if style == "minimal":
        print(f"{result['file']}: {rating} ({conf:.0%})")
        return
    
    if style == "json":
        print(json.dumps(result, indent=2))
        return
    
    # Default: Box-Format
    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════
║  SPOTILYZER ANALYSIS
╠═══════════════════════════════════════════════════════════════════════════════
║  Track:       {result['file'][:50]}
║
║  Bewertung:   {emoji} {rating}
║  Konfidenz:   [{bar}] {conf:.1%}
║
║  Wahrscheinlichkeiten:
║    🔥 Hit:    {probs.get('hit', 0):>6.1%}
║    ➖ Mid:    {probs.get('mid', 0):>6.1%}
║    💀 Flop:   {probs.get('flop', 0):>6.1%}
╚═══════════════════════════════════════════════════════════════════════════════
""")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Analysiere einen Track auf Hit-Potenzial"
    )
    parser.add_argument(
        "track",
        type=str,
        help="Pfad zur Audio-Datei (MP3, WAV, FLAC, etc.)"
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_PATH,
        help=f"Pfad zum trainierten Modell (default: {DEFAULT_MODEL_PATH})"
    )
    parser.add_argument(
        "--style",
        choices=["default", "minimal", "json"],
        default="default",
        help="Output-Stil (default: default)"
    )
    parser.add_argument(
        "--device",
        choices=["cuda", "cpu", "auto"],
        default="auto",
        help="Device für MERT (default: auto)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Weniger Output während Verarbeitung"
    )
    args = parser.parse_args()

    track_path = Path(args.track)
    model_path = Path(args.model)
    
    # Validierung
    if not track_path.exists():
        print(f"Fehler: Datei nicht gefunden: {track_path}")
        sys.exit(1)
    
    if not model_path.exists():
        print(f"Fehler: Modell nicht gefunden: {model_path}")
        print(f"→ Erst 'python train_model.py' ausführen!")
        sys.exit(1)
    
    # Modell laden
    if not args.quiet:
        print(f"  Lade Modell: {model_path}")
    model_data = joblib.load(model_path)
    
    # MERT laden
    if not args.quiet:
        print(f"  Lade MERT ({args.device})...")
    device = args.device if args.device != "auto" else None
    embedder = MERTEmbedder(device)
    
    # Analyse
    if not args.quiet:
        print(f"\n  Analysiere: {track_path.name}")
    
    result = analyze_track(track_path, model_data, embedder, verbose=not args.quiet)
    
    # Output
    print_result(result, style=args.style)


if __name__ == "__main__":
    main()
