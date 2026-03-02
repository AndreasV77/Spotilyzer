import os
import argparse
import pandas as pd
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

def get_spotify_client():
    load_dotenv()
    scope = "user-read-private"
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        scope=scope,
        open_browser=True
    ))

def fetch_features_for_track(sp, track_id):
    # Accept full URL or bare ID
    if track_id.startswith("http"):
        track_id = track_id.split("/")[-1].split("?")[0]
    track = sp.track(track_id)
    feats = sp.audio_features([track_id])[0]
    analysis = sp.audio_analysis(track_id)  # optional, richer sections
    row = {
        "track_id": track_id,
        "track_name": track["name"],
        "artist": ", ".join([a["name"] for a in track["artists"]]),
        "album": track["album"]["name"],
        "duration_ms": track["duration_ms"],
        "popularity": track.get("popularity"),
    }
    if feats:
        row.update({
            "danceability": feats["danceability"],
            "energy": feats["energy"],
            "valence": feats["valence"],
            "tempo": feats["tempo"],
            "loudness": feats["loudness"],
            "key": feats["key"],
            "mode": feats["mode"],
            "time_signature": feats["time_signature"],
            "speechiness": feats["speechiness"],
            "acousticness": feats["acousticness"],
            "instrumentalness": feats["instrumentalness"],
            "liveness": feats["liveness"],
        })
    # Example: intro length from analysis sections
    try:
        sections = analysis.get("sections", [])
        intro_end = sections[1]["start"] if len(sections) > 1 else None
        row["intro_end_sec"] = intro_end
    except Exception:
        row["intro_end_sec"] = None
    return row

def search_track_id(sp, title, artist=None):
    q = f'track:"{title}"'
    if artist:
        q += f' artist:"{artist}"'
    res = sp.search(q, type="track", limit=1)
    items = res.get("tracks", {}).get("items", [])
    if items:
        return items[0]["id"]
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inpath", help="CSV with column 'track' (ID/URL)")
    parser.add_argument("--search", dest="searchpath", help="CSV with columns 'title','artist'")
    parser.add_argument("--out", dest="outpath", default="spotify_features.csv")
    args = parser.parse_args()

    sp = get_spotify_client()

    rows = []
    if args.inpath:
        df = pd.read_csv(args.inpath)
        for t in df["track"].dropna():
            try:
                rows.append(fetch_features_for_track(sp, str(t)))
            except Exception as e:
                rows.append({"track_id": t, "error": str(e)})
    elif args.searchpath:
        df = pd.read_csv(args.searchpath)
        for _, r in df.iterrows():
            tid = search_track_id(sp, str(r.get("title","")).strip(), str(r.get("artist","")).strip() or None)
            if tid:
                try:
                    rows.append(fetch_features_for_track(sp, tid))
                except Exception as e:
                    rows.append({"track_query": f'{r.get("title")} - {r.get("artist")}', "error": str(e)})
            else:
                rows.append({"track_query": f'{r.get("title")} - {r.get("artist")}', "error": "not found"})
    else:
        raise SystemExit("Provide --in or --search")

    out = pd.DataFrame(rows)
    out.to_csv(args.outpath, index=False)
    print(f"Wrote {args.outpath} with {len(out)} rows.")

if __name__ == "__main__":
    main()
