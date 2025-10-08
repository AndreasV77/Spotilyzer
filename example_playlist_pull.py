# example_playlist_pull.py
# Minimal, robust: zieht Tracks + Audio Features aus einer Spotify-Playlist
# Auth: Client Credentials (öffentlich) oder -U für User OAuth (private)

THROTTLE_BULK = 0.02         # vorher: 0.05
RETRY_429_BULK = 2.0
RETRY_429_SINGLE = 1.5
RETRY_MISC_SLEEP = 0.5

import os
import re
import sys
import time
from typing import Iterable, List, Dict

import pandas as pd
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

load_dotenv()

def log_err(msg: str):
    print(msg, file=sys.stderr, flush=True)


def norm_playlist_id(s: str) -> str:
    # URL/URI -> reine 22er ID
    m = re.search(r"(playlist/|:playlist:)?([A-Za-z0-9]{22})", s)
    if not m:
        raise ValueError(f"Keine gültige Playlist-ID/URL/URI: {s}")
    return m.group(2)


def get_sp(use_user: bool = False):
    if use_user:
        scope = "playlist-read-private playlist-read-collaborative"
        return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))
    else:
        return spotipy.Spotify(auth_manager=SpotifyClientCredentials())


def find_spotify_playlist_id(sp, name: str, market: str | None = None) -> str:
    """
    Sucht eine öffentliche Playlist per Name.
    Bevorzugt Owner 'spotify', toleriert None-Items und liefert
    bei Mehrdeutigkeiten das beste Match.
    """
    q = name.strip()
    limit = 50
    got = []

    res = sp.search(q=q, type="playlist", limit=limit, market=market)
    while True:
        pls = (res.get("playlists") or {}).get("items") or []
        for it in pls:
            if not isinstance(it, dict):
                continue
            pid = it.get("id")
            pname = (it.get("name") or "").strip()
            owner = it.get("owner") or {}
            owner_id = owner.get("id") or ""
            owner_name = (owner.get("display_name") or "")
            if not pid:
                continue
            got.append({
                "id": pid,
                "name": pname,
                "owner_id": owner_id,
                "owner_name": owner_name,
            })
        nxt = (res.get("playlists") or {}).get("next")
        if not nxt:
            break
        # wichtig: sp.next auf dem Unterobjekt aufrufen
        res["playlists"] = sp.next(res["playlists"])

    if not got:
        raise ValueError(f"Playlist nicht gefunden: {name}")

    # 1) exakter Name + Owner spotify
    for g in got:
        if g["name"].lower() == q.lower() and (g["owner_id"] == "spotify" or g["owner_name"] == "Spotify"):
            return g["id"]
    # 2) Owner spotify bevorzugen
    for g in got:
        if g["owner_id"] == "spotify" or g["owner_name"] == "Spotify":
            return g["id"]
    # 3) bestes verfügbares Match
    return got[0]["id"]


    def iter_playlist_tracks(sp, playlist_id: str, market: str | None = None) -> Iterable[Dict]:
        fields = "items(added_at,track(id,name,artists(name),album(name),duration_ms,available_markets)),next,total"
        kwargs = {"additional_types": ("track",), "fields": fields}
        if market:
            kwargs["market"] = market
        page = sp.playlist_items(playlist_id, **kwargs)
        while True:
            for it in page.get("items", []):
                tr = it.get("track")
                if not tr or tr.get("id") is None:
                    continue
                yield tr
            nxt = page.get("next")
            if not nxt:
                break
            page = sp.next(page)


    def audio_features_chunked(sp, ids: List[str]) -> List[Dict]:
        out: List[Dict] = []

    def get_bulk(chunk: List[str]) -> List[Dict]:
        feats = sp.audio_features(chunk) or []
        # Spotipy gibt Liste mit Dicts oder None zurück → None filtern
        return [f for f in feats if isinstance(f, dict)]

    def get_single(track_id: str) -> Dict:
        feats = sp.audio_features([track_id]) or []
        f = feats[0] if feats else None
        return f if isinstance(f, dict) and f.get("id") else {}


    def fetch_block(block_ids: List[str]) -> List[Dict]:
        try:
            return get_bulk(block_ids)
        except spotipy.exceptions.SpotifyException as e:
            status = getattr(e, "http_status", None)
            if status == 429:
                # konservativer Backoff, dann Bulk erneut
                log_err("⏳ 429 (Rate limit) – kurzer Backoff, versuche Bulk erneut …")
                time.sleep(RETRY_429_BULK)
                try:
                    return get_bulk(block_ids)
                except spotipy.exceptions.SpotifyException:
                    pass
            if status == 403:
                # einzeln versuchen
                feats: List[Dict] = []
                for tid in block_ids:
                    for attempt in range(2):
                        try:
                            f = get_single(tid)
                            if f:
                                feats.append(f)
                            break
                        except spotipy.exceptions.SpotifyException as e2:
                            s2 = getattr(e2, "http_status", None)
                            if s2 == 429:
                                time.sleep(RETRY_429_SINGLE)
                                continue
                            if s2 == 403:
                                log_err(f"⚠️ 403 auf ID {tid} – skip.")
                                break
                            time.sleep(0.5)
                            break
                return feats
            # andere Fehler: kurz warten, leer zurück (Pipeline soll weiterlaufen)
            time.sleep(RETRY_MISC_SLEEP)
            return []

    for i in range(0, len(ids), 100):
        chunk = ids[i:i+100]
        out.extend(fetch_block(chunk))
        time.sleep(0.05)  # sanftes Throttling

    return out


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--playlist-id", help="Playlist-ID/URL/URI")
    ap.add_argument("--playlist-name", help="Playlist-Name (Owner=Spotify bevorzugt)")
    ap.add_argument("--market", choices=["DE", "US", "GB"], help="z. B. DE/US/GB")
    ap.add_argument("-U", "--user-auth", action="store_true", help="Authorization Code Flow verwenden")
    ap.add_argument("--out", default="playlist_features.csv")
    ap.add_argument("--force", action="store_true",
                help="Existierende Ausgabedatei ohne Rückfrage überschreiben")
    args = ap.parse_args()

    sp = get_sp(use_user=args.user_auth)

    if args.playlist_id:
        pid = norm_playlist_id(args.playlist_id)
    elif args.playlist_name:
        pid = find_spotify_playlist_id(sp, args.playlist_name, market=args.market)
    else:
        ap.error("Bitte --playlist-id oder --playlist-name angeben")

    tracks = list(iter_playlist_tracks(sp, pid, market=args.market))
    if not tracks:
        log_err("Hinweis: Keine Tracks (Markt-Filter?). Ohne --market erneut probieren.", file=sys.stderr)

    rows = []
    for tr in tracks:
        tid = tr["id"]
        rows.append({
            "track_id": tid,
            "track_name": tr.get("name"),
            "artist": ", ".join(a["name"] for a in tr.get("artists", [])),
            "album": tr.get("album", {}).get("name"),
            "duration_ms": tr.get("duration_ms"),
        })
    base = pd.DataFrame(rows).drop_duplicates("track_id")

    feats = audio_features_chunked(sp, base["track_id"].tolist())
    fdf = pd.DataFrame(feats if feats else [])

    if "id" in fdf.columns:
        fdf = fdf.dropna(subset=["id"])
        out = base.merge(fdf, left_on="track_id", right_on="id", how="left")
        got = fdf["id"].nunique(); total = base["track_id"].nunique()
        print(f"Features erhalten: {got}/{total} ({100*got/max(total,1):.1f}%)")
    else:
        log_err("⚠️ Keine Audio Features erhalten – evtl. 403 oder API-Limit.")
        out = base.copy()

    out.to_csv(args.out, index=False, encoding="utf-8")
    print(f"OK → {args.out} ({len(out)} Zeilen)")

    if __name__ == "__main__":
        # Debug: zeigt dir, welche Datei gerade ausgeführt wird
        print(f"Running: {__file__}  (cwd={os.getcwd()})")
        main()