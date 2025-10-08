# score_rank.py
# Scoring lokaler Songs gegen Referenz-Clusters (mean/std) -> ranking.csv
import pandas as pd
import numpy as np

CORE = ["tempo","energy","valence","loudness","danceability"]

def load_stats(path: str) -> pd.DataFrame:
    """
    Erwartet wide-Format:
      cluster, tempo_mean, tempo_std, energy_mean, energy_std, ...
    Alternativ long-Format:
      cluster, feature, mean, std   (wird gepivotet)
    """
    df = pd.read_csv(path)
    cols = set(df.columns.str.lower())
    # long -> wide pivot
    if {"feature","mean","std","cluster"}.issubset(cols):
        tmp = df.copy()
        tmp.columns = [c.lower() for c in tmp.columns]
        wide = tmp.pivot_table(index="cluster", columns="feature", values=["mean","std"])
        wide.columns = [f"{f}_{sfx}" for sfx, f in wide.columns]
        wide = wide.reset_index()
        return wide
    return df

def pick_features(local_cols, stats_cols, requested):
    feats = []
    for f in requested:
        if f in local_cols and (f+"_mean" in stats_cols) and (f+"_std" in stats_cols):
            feats.append(f)
    return feats

def safe_z(x, mu, sd):
    sd = sd if (sd is not None and sd > 1e-8) else 1.0
    return (x - mu) / sd

def diag_line(f, x, mu, unit=""):
    diff = x - mu
    if unit == "bpm":
        return f"Tempo {('+' if diff>=0 else '')}{diff:.1f} bpm gg. Ref"
    if unit == "dB":
        return f"Loudness {('+' if diff>=0 else '')}{diff:.1f} dB gg. Ref"
    # normierte 0..1 Features als Δ in Prozentpunkten
    return f"{f.capitalize()} {('+' if diff>=0 else '')}{(diff*100):.1f} pp gg. Ref"

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", required=True, help="local_features.csv")
    ap.add_argument("--stats", required=True, nargs="+", help="genre_*_stats.csv oder playlist_*_stats.csv (eine oder mehrere)")
    ap.add_argument("--features", nargs="+", default=CORE, help="Feature-Liste in Priorität")
    ap.add_argument("--weights", nargs="*", default=None, help="optional: f=w  z.B. tempo=1 loudness=1 energy=0.8")
    ap.add_argument("--out", default="ranking.csv")
    args = ap.parse_args()

    loc = pd.read_csv(args.local)
    # lokale Spalten vereinheitlichen
    loc.columns = [c.strip() for c in loc.columns]
    # bekannte Alias-Übersetzungen (falls lokal z.B. tempo_bpm)
    if "tempo_bpm" in loc.columns and "tempo" not in loc.columns:
        loc["tempo"] = loc["tempo_bpm"].astype(float)
    if "lufs" in loc.columns and "loudness" not in loc.columns:
        # LUFS ~ Loudness (negativ). Wenn du LUFS hast, nimm es als loudness-Ersatz.
        loc["loudness"] = loc["lufs"].astype(float)

    stats_list = [load_stats(p) for p in args.stats]
    stats = pd.concat(stats_list, ignore_index=True)

    # Gewichte parsen
    w = {f:1.0 for f in args.features}
    if args.weights:
        for kv in args.weights:
            if "=" in kv:
                k,v = kv.split("=",1)
                try:
                    w[k.strip()] = float(v)
                except:
                    pass

    # verwendbare Features: Schnittmenge
    usable = pick_features(set(loc.columns), set(stats.columns), args.features)
    if not usable:
        raise SystemExit("Keine gemeinsamen Features zwischen local und stats gefunden.")

    # für jedes Cluster Distanz berechnen
    clusters = stats["cluster"].tolist()
    records = []
    for i, row in loc.iterrows():
        x = {f: row.get(f, np.nan) for f in usable}
        best = None
        best_d = None
        best_diag = None
        for _, s in stats.iterrows():
            d2 = 0.0
            diag = []
            for f in usable:
                mu = s.get(f+"_mean", np.nan)
                sd = s.get(f+"_std", np.nan)
                if pd.isna(x[f]) or pd.isna(mu) or pd.isna(sd):
                    continue
                z = safe_z(float(x[f]), float(mu), float(sd))
                d2 += (w.get(f,1.0) * z) ** 2
                unit = "bpm" if f=="tempo" else ("dB" if f=="loudness" else "")
                diag.append(diag_line(f, float(x[f]), float(mu), unit=unit))
            if best_d is None or d2 < best_d:
                best_d = d2
                best = s["cluster"]
                best_diag = "; ".join(diag)
        records.append({
            "track_id": row.get("track_id"),
            "track_name": row.get("track_name"),
            "artist": row.get("artist"),
            "used_features": ",".join(usable),
            "assigned_cluster": best,
            "distance": best_d,
            "diagnosis": best_diag
        })
    out = pd.DataFrame(records).sort_values("distance", ascending=True).reset_index(drop=True)
    out.to_csv(args.out, index=False, encoding="utf-8")
    print(f"OK → {args.out} ({len(out)} Zeilen). Features: {', '.join(usable)}")

if __name__ == "__main__":
    main()
