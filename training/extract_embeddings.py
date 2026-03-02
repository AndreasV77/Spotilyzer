"""
extract_embeddings.py
=====================
Extrahiert MERT-Embeddings aus den heruntergeladenen Preview-MP3s.

MERT (Music undERstanding Transformer) ist ein auf Musik spezialisiertes
Audio-Modell von m-a-p (Music and Audio Processing Lab).

Input: Verzeichnis mit MP3-Dateien (cluster_trackid.mp3)
Output: NumPy-Array mit Embeddings + Metadaten-CSV

Autor: Claude Opus (für Andreas Vogelsang)
Datum: 2026-03-02

GPU-Empfehlung: MERT auf GPU: <1s pro Track, auf CPU: ~10-15s pro Track
"""

import sys
import time
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
import torch
import torchaudio
from tqdm import tqdm
from transformers import AutoModel, AutoProcessor

# ══════════════════════════════════════════════════════════════════════════════
# KONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_INPUT = "previews"
DEFAULT_OUTPUT = "embeddings"
MODEL_NAME = "m-a-p/MERT-v1-95M"  # ~380MB, musik-optimiert

# Audio-Konfiguration (MERT erwartet 24kHz)
TARGET_SAMPLE_RATE = 24000
MAX_AUDIO_LENGTH_SEC = 30  # Previews sind ~30s


# ══════════════════════════════════════════════════════════════════════════════
# MERT-MODELL
# ══════════════════════════════════════════════════════════════════════════════

class MERTEmbedder:
    """Wrapper für MERT-Embedding-Extraktion."""
    
    def __init__(self, model_name: str = MODEL_NAME, device: str = None):
        """
        Initialisiert das MERT-Modell.
        
        Args:
            model_name: HuggingFace Model-ID
            device: 'cuda', 'cpu', oder None (auto-detect)
        """
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        print(f"  Lade MERT-Modell auf {self.device.upper()}...")
        
        self.processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(model_name, trust_remote_code=True)
        self.model.to(self.device)
        self.model.eval()
        
        print(f"  Modell geladen: {model_name}")
    
    def load_audio(self, filepath: Path) -> torch.Tensor | None:
        """
        Lädt und preprocessed eine Audio-Datei.
        
        Returns:
            Tensor mit Audio-Daten oder None bei Fehler
        """
        try:
            waveform, sample_rate = torchaudio.load(filepath)
            
            # Mono konvertieren falls Stereo
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
            
            # Resample auf 24kHz falls nötig
            if sample_rate != TARGET_SAMPLE_RATE:
                resampler = torchaudio.transforms.Resample(
                    orig_freq=sample_rate,
                    new_freq=TARGET_SAMPLE_RATE
                )
                waveform = resampler(waveform)
            
            # Auf maximale Länge begrenzen
            max_samples = TARGET_SAMPLE_RATE * MAX_AUDIO_LENGTH_SEC
            if waveform.shape[1] > max_samples:
                waveform = waveform[:, :max_samples]
            
            return waveform.squeeze(0)  # [samples]
            
        except Exception as e:
            print(f"    Fehler beim Laden von {filepath.name}: {e}", file=sys.stderr)
            return None
    
    @torch.no_grad()
    def extract_embedding(self, waveform: torch.Tensor) -> np.ndarray | None:
        """
        Extrahiert das Embedding für eine Waveform.
        
        Returns:
            NumPy-Array mit Shape [768] oder None bei Fehler
        """
        try:
            # Processor anwenden
            inputs = self.processor(
                waveform.numpy(),
                sampling_rate=TARGET_SAMPLE_RATE,
                return_tensors="pt"
            )
            
            # Auf Device verschieben
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Forward pass
            outputs = self.model(**inputs, output_hidden_states=True)
            
            # Letzten Hidden State nehmen und über Zeit mitteln
            # outputs.last_hidden_state: [batch, time, 768]
            hidden_states = outputs.last_hidden_state
            embedding = hidden_states.mean(dim=1).squeeze(0)  # [768]
            
            return embedding.cpu().numpy()
            
        except Exception as e:
            print(f"    Fehler bei Embedding-Extraktion: {e}", file=sys.stderr)
            return None
    
    def process_file(self, filepath: Path) -> np.ndarray | None:
        """
        Kompletter Pipeline: Laden → Embedding extrahieren.
        
        Returns:
            NumPy-Array mit Shape [768] oder None bei Fehler
        """
        waveform = self.load_audio(filepath)
        if waveform is None:
            return None
        
        return self.extract_embedding(waveform)


# ══════════════════════════════════════════════════════════════════════════════
# BATCH-VERARBEITUNG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EmbeddingRecord:
    """Metadaten für ein Embedding."""
    track_id: int
    cluster: str
    filename: str
    embedding_idx: int  # Index im NumPy-Array


def parse_filename(filename: str) -> tuple[str, int] | None:
    """
    Parst cluster_trackid.mp3 zu (cluster, track_id).
    
    Returns:
        (cluster, track_id) oder None bei ungültigem Format
    """
    if not filename.endswith(".mp3"):
        return None
    
    name = filename[:-4]  # .mp3 entfernen
    parts = name.rsplit("_", 1)  # Letzten Underscore splitten
    
    if len(parts) != 2:
        return None
    
    cluster, track_id_str = parts
    
    try:
        track_id = int(track_id_str)
        return (cluster, track_id)
    except ValueError:
        return None


def process_batch(
    embedder: MERTEmbedder,
    input_dir: Path,
    output_dir: Path,
    limit: int = 0,
    cluster_filter: str = None
) -> dict:
    """
    Verarbeitet alle MP3s im Input-Verzeichnis.
    
    Args:
        embedder: MERT-Embedder-Instanz
        input_dir: Verzeichnis mit MP3s
        output_dir: Zielverzeichnis für Embeddings
        limit: Maximale Anzahl (0 = alle)
        cluster_filter: Nur bestimmten Cluster verarbeiten
    
    Returns:
        Stats-Dict
    """
    # MP3s finden
    mp3_files = sorted(input_dir.glob("*.mp3"))
    
    if cluster_filter:
        mp3_files = [f for f in mp3_files if f.name.startswith(f"{cluster_filter}_")]
    
    if limit > 0:
        mp3_files = mp3_files[:limit]
    
    if not mp3_files:
        print("  Keine MP3-Dateien gefunden!")
        return {"success": 0, "failed": 0}
    
    print(f"  Verarbeite {len(mp3_files)} Dateien...")
    
    # Ergebnis-Container
    embeddings_list = []
    records = []
    stats = {"success": 0, "failed": 0, "errors": []}
    
    # Verarbeitung mit Fortschrittsbalken
    start_time = time.time()
    
    for idx, filepath in enumerate(tqdm(mp3_files, desc="Extracting", unit="file")):
        parsed = parse_filename(filepath.name)
        if parsed is None:
            stats["failed"] += 1
            stats["errors"].append((filepath.name, "invalid filename"))
            continue
        
        cluster, track_id = parsed
        
        # Embedding extrahieren
        embedding = embedder.process_file(filepath)
        
        if embedding is None:
            stats["failed"] += 1
            stats["errors"].append((filepath.name, "extraction failed"))
            continue
        
        # Speichern
        embeddings_list.append(embedding)
        records.append(EmbeddingRecord(
            track_id=track_id,
            cluster=cluster,
            filename=filepath.name,
            embedding_idx=len(embeddings_list) - 1
        ))
        stats["success"] += 1
    
    elapsed = time.time() - start_time
    
    # Als NumPy-Array speichern
    if embeddings_list:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Embeddings als .npy
        embeddings_array = np.stack(embeddings_list, axis=0)
        embeddings_path = output_dir / "embeddings.npy"
        np.save(embeddings_path, embeddings_array)
        
        # Metadaten als CSV
        records_df = pd.DataFrame([asdict(r) for r in records])
        records_path = output_dir / "embeddings_meta.csv"
        records_df.to_csv(records_path, index=False)
        
        # Info-JSON
        info = {
            "model": MODEL_NAME,
            "embedding_dim": embeddings_array.shape[1],
            "num_embeddings": embeddings_array.shape[0],
            "sample_rate": TARGET_SAMPLE_RATE,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "processing_time_sec": round(elapsed, 1),
            "avg_time_per_file_sec": round(elapsed / len(mp3_files), 2),
        }
        info_path = output_dir / "embeddings_info.json"
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)
        
        print(f"\n  Gespeichert:")
        print(f"    {embeddings_path} ({embeddings_array.shape})")
        print(f"    {records_path}")
        print(f"    {info_path}")
    
    stats["elapsed"] = elapsed
    return stats


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Extrahiere MERT-Embeddings aus Preview-MP3s"
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help=f"Input-Verzeichnis mit MP3s (default: {DEFAULT_INPUT})"
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output-Verzeichnis für Embeddings (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximale Anzahl zu verarbeiten (0 = alle)"
    )
    parser.add_argument(
        "--cluster",
        type=str,
        default=None,
        help="Nur bestimmten Cluster verarbeiten"
    )
    parser.add_argument(
        "--device",
        choices=["cuda", "cpu", "auto"],
        default="auto",
        help="Device für MERT (default: auto)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Zeige was verarbeitet würde, ohne tatsächlich zu laden"
    )
    args = parser.parse_args()

    print(f"═══════════════════════════════════════════════════════════════════════════════")
    print(f"  MERT EMBEDDING EXTRACTOR")
    print(f"═══════════════════════════════════════════════════════════════════════════════")
    
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    
    if not input_dir.exists():
        print(f"  Fehler: Input-Verzeichnis nicht gefunden: {input_dir}")
        sys.exit(1)
    
    # MP3s zählen
    mp3_files = list(input_dir.glob("*.mp3"))
    if args.cluster:
        mp3_files = [f for f in mp3_files if f.name.startswith(f"{args.cluster}_")]
    
    print(f"  Input:     {input_dir}")
    print(f"  MP3s:      {len(mp3_files)}")
    print(f"  Output:    {output_dir}")
    
    if args.cluster:
        print(f"  Filter:    cluster={args.cluster}")
    if args.limit > 0:
        print(f"  Limit:     {args.limit}")
    
    # Device
    device = args.device if args.device != "auto" else None
    actual_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  Device:    {actual_device.upper()}")
    
    if actual_device == "cuda":
        print(f"  GPU:       {torch.cuda.get_device_name(0)}")
        print(f"  VRAM:      {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    
    # Geschätzte Zeit
    time_per_file = 0.8 if actual_device == "cuda" else 12.0
    total_files = min(len(mp3_files), args.limit) if args.limit > 0 else len(mp3_files)
    est_minutes = total_files * time_per_file / 60
    print(f"\n  Geschätzte Zeit: ~{est_minutes:.0f} Minuten")
    
    if args.dry_run:
        print(f"\n  [DRY RUN] Keine Verarbeitung durchgeführt.")
        return
    
    # Modell laden und verarbeiten
    print()
    embedder = MERTEmbedder(MODEL_NAME, device)
    print()
    
    stats = process_batch(
        embedder,
        input_dir,
        output_dir,
        limit=args.limit,
        cluster_filter=args.cluster
    )
    
    # Ergebnis
    print(f"\n{'─'*79}")
    print(f"  EXTRACTION COMPLETE")
    print(f"{'─'*79}")
    print(f"  Erfolgreich:    {stats['success']:>5}")
    print(f"  Fehlgeschlagen: {stats['failed']:>5}")
    print(f"  Zeit:           {stats.get('elapsed', 0):.1f}s ({stats.get('elapsed', 0)/60:.1f} min)")
    
    if stats['success'] > 0:
        print(f"  Durchschnitt:   {stats.get('elapsed', 0)/stats['success']:.2f}s pro Datei")
    
    if stats.get("errors"):
        print(f"\n  Fehler (erste 5):")
        for filename, error in stats["errors"][:5]:
            print(f"    {filename}: {error}")


if __name__ == "__main__":
    main()
