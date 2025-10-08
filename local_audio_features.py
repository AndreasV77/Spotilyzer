import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

# Heavy libs:
# librosa for MIR, pyloudnorm for LUFS
try:
    import librosa
    import pyloudnorm as pyln
except Exception as e:
    raise SystemExit("Please install librosa and pyloudnorm: pip install librosa pyloudnorm") from e

def estimate_key(y, sr):
    # Very rough key estimate via chroma peaks
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    key_index = chroma.mean(axis=1).argmax()
    key_names = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
    return key_names[int(key_index)]

def lufs_integrated(y, sr):
    meter = pyln.Meter(sr)  # EBU R128
    return meter.integrated_loudness(y)

def analyze_file(path: Path):
    y, sr = librosa.load(path, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)
    # Tempo (BPM)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    # Spectral centroid (brightness proxy)
    sc = librosa.feature.spectral_centroid(y=y, sr=sr)
    sc_mean = float(np.mean(sc))
    # RMS loudness proxy
    rms = librosa.feature.rms(y=y)
    rms_mean = float(np.mean(rms))
    # Dynamic variance (energy variability)
    dyn_var = float(np.var(rms))
    # LUFS integrated
    lufs = float(lufs_integrated(y, sr))
    # Key (very rough)
    key = estimate_key(y, sr)
    return {
        "file": str(path.name),
        "duration_sec": float(duration),
        "tempo_bpm": float(np.atleast_1d(tempo)[0]),
        "spectral_centroid_mean": sc_mean,
        "rms_mean": rms_mean,
        "energy_variance": dyn_var,
        "lufs_i": lufs,
        "key_est": key,
        "samplerate": sr,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="indir", required=True, help="Folder with audio files")
    ap.add_argument("--out", dest="out", default="local_features.csv")
    args = ap.parse_args()

    p = Path(args.indir)
    rows = []
    for ext in ("*.wav","*.mp3","*.flac","*.m4a","*.ogg"):
        for f in p.glob(ext):
            try:
                rows.append(analyze_file(f))
            except Exception as e:
                rows.append({"file": f.name, "error": str(e)})

    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False)
    print(f"Wrote {args.out} with {len(df)} rows.")

if __name__ == "__main__":
    main()
