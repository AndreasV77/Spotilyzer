# build_genre_ref_stats.py
# Baut Referenzdaten via Recommendations (seed_genres) pro Markt und berechnet mean/std je Genre.
import os, time
import pandas as pd
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()

GENRES = ["pop","rock","metal","techno","house"]  # erweiterbar
N_PER_GENRE = 150  # 5*150 = 750 Tracks je Market, in 100er Häppchen holen

def get_sp():
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials())

def get_reco_tracks(sp, genre: str, market: str) -> pd.DataFrame:
    rows = []
    fetched = 0
    while fetched < N_PER_GENRE:
        limit = min(100, N_PER_GENRE - fetched)
        rec = sp.recommendations(seed_genres=[genre], limit=limit, market=market)
        tids = [t["id"] for t in rec.get("tracks", []) if t.get("id")]
        if not tids:
            break
        feats = sp.audio_features(tids) or []
        for t, f in zip(rec["tracks"], feats):
            if not f: 
                continue
            rows.append({
                "genre": genre,
                "market": market,
                "track_id": t["id"],
                "track_name": t["name"],
                "artist": ", ".join(a["name"] for a in t.get("artists", [])),
                "tempo": f.get("tempo"),
                "energy": f.get("energy"),
                "valence": f.get("valence"),
                "loudness": f.get("loudness"),
                "danceability": f.get("danceability"),
            })
        fetched += len(tids)
        time.sleep(0.05)
    return pd.DataFrame(rows)

def main():
    import argparse, pathlib
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", nargs="+", default=["DE","US","GB"])
    ap.add_argument("--genres", nargs="+", default=GENRES)
    ap.add_argument("--outdir", default="refdata")
    args = ap.parse_args()

    sp = get_sp()
    pathlib.Path(args.outdir).mkdir(parents=True, exist_ok=True)
    for m in args.markets:
        frames = []
        for g in args.genres:
            df = get_reco_tracks(sp, g, m)
            frames.append(df)
        feats = pd.concat(frames, ignore_index=True)
        feats.to_csv(f"{args.outdir}/genre_{m}_features.csv", index=False, encoding="utf-8")

        # Stats je Genre: mean/std für Kernfeatures
        stat = feats.groupby("genre")[["tempo","energy","valence","loudness","danceability"]].agg(["mean","std"])
        # Wide flatten
        stat.columns = [f"{c}_{sfx}" for c, sfx in stat.columns]
        stat = stat.reset_index().rename(columns={"genre":"cluster"})
        stat.to_csv(f"{args.outdir}/genre_{m}_stats.csv", index=False, encoding="utf-8")
        print(f"OK → {args.outdir}/genre_{m}_features.csv + genre_{m}_stats.csv")

if __name__ == "__main__":
    main()
