import os
import sys
import time
import argparse
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import pandas as pd
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
from spotipy.exceptions import SpotifyException

DEFAULT_PLAYLISTS = [
    "37i9dQZEVXbMDoHDwVN2tF",  # Top 50 Global
    "37i9dQZF1DWXRqgorJj26U",  # Rock This
    "37i9dQZF1DWXLeA8Omikj7",  # Kickass Metal
    "37i9dQZF1DX6J5NfMJS675",  # Techno Bunker
    "37i9dQZF1DX2TRYkJECvfC",  # Housewerk
]

MARKETS = {"DE":"DE", "US":"US", "UK":"GB"}

AUDIO_FEAT_COLS = [
    "danceability","energy","valence","tempo","loudness","key","mode",
    "time_signature","speechiness","acousticness","instrumentalness","liveness"
]

MAX_RETRIES = 5
REQUEST_SLEEP = 0.02


class ApiMetrics:
    def __init__(self):
        self.retries_429 = 0
        self.skipped_404 = 0


def api_call_with_retries(fn, metrics: ApiMetrics, context: str, *args, **kwargs):
    retries_429 = 0
    retries_5xx = 0
    while True:
        try:
            result = fn(*args, **kwargs)
            if REQUEST_SLEEP:
                time.sleep(REQUEST_SLEEP)
            return result
        except SpotifyException as e:
            status = getattr(e, "http_status", None)
            headers = getattr(e, "headers", {})
            if status == 429 and retries_429 < MAX_RETRIES:
                retry_after = headers.get("Retry-After") if isinstance(headers, dict) else None
                try:
                    sleep_s = float(retry_after) if retry_after is not None else 1.0
                except (TypeError, ValueError):
                    sleep_s = 1.0
                metrics.retries_429 += 1
                print(f"[WARN] 429 rate limited for {context} → retry in {sleep_s:.2f}s", file=sys.stderr)
                time.sleep(sleep_s)
                retries_429 += 1
                continue
            if status == 404:
                metrics.skipped_404 += 1
                print(f"[WARN] 404 not found for {context}: {e}", file=sys.stderr)
                return None
            if status and 500 <= status < 600 and retries_5xx < 1:
                retries_5xx += 1
                print(
                    f"[WARN] Spotify API error (status={status}) for {context}, retrying once: {e}",
                    file=sys.stderr,
                )
                time.sleep(1.0)
                continue
            print(f"[ERROR] Spotify API error for {context} (status={status}): {e}", file=sys.stderr)
            raise


def get_spotify_client(use_client_credentials: bool):
    load_dotenv()
    if use_client_credentials:
        auth = SpotifyClientCredentials(
            client_id=os.getenv("SPOTIPY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        )
        return spotipy.Spotify(auth_manager=auth)
    scope = "playlist-read-private user-read-private"
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        scope=scope,
        open_browser=True
    ))

def extract_playlist_id_or_name(s: str):
    # Accept URL → ID, bare ID, or plain name (return name flag)
    if s.startswith("http"):
        path = urlparse(s).path.strip("/")
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] == "playlist":
            return parts[1], None
        return parts[-1], None
    # looks like an ID (22 chars, mostly base62)
    if len(s) in (22, 23) and s.replace("_","").isalnum():
        return s, None
    # else treat as a name to search
    return None, s

def resolve_playlist_id_from_name(sp, metrics: ApiMetrics, name: str, market: str):
    q = f'playlist:"{name}"'
    res = api_call_with_retries(sp.search, metrics, f"search playlist name={name!r}", q, type="playlist", limit=5, market=market)
    if res is None:
        return None, None
    items = res.get("playlists", {}).get("items", [])
    if not items:
        # try without quotes
        res = api_call_with_retries(sp.search, metrics, f"search playlist fallback name={name!r}", name, type="playlist", limit=5, market=market)
        if res is None:
            return None, None
        items = res.get("playlists", {}).get("items", [])
    if items:
        # choose official Spotify-owned first if present
        items_sorted = sorted(items, key=lambda x: (x.get("owner",{}).get("id")!="spotify", -x.get("followers",{}).get("total",0)))
        return items_sorted[0]["id"], items_sorted[0]["name"]
    return None, None

def fetch_all_playlist_tracks(sp, metrics: ApiMetrics, playlist_id: str, market: str):
    results = api_call_with_retries(
        sp.playlist_items,
        metrics,
        f"playlist_items {playlist_id}",
        playlist_id,
        additional_types="track",
        limit=100,
        market=market,
    )
    if results is None:
        return []
    items = results.get("items", [])
    while results.get("next"):
        results = api_call_with_retries(sp.next, metrics, f"playlist_items next {playlist_id}", results)
        if results is None:
            break
        items.extend(results.get("items", []))
    tracks = []
    for it in items:
        tr = it.get("track")
        if tr and tr.get("id"):
            tracks.append(tr)
    return tracks

def fetch_audio_features(sp, metrics: ApiMetrics, track_ids):
    feats = []
    for i in range(0, len(track_ids), 100):
        batch = track_ids[i:i+100]
        batch_feats = api_call_with_retries(sp.audio_features, metrics, f"audio_features batch starting {batch[0] if batch else 'empty'}", batch)
        if batch_feats is None:
            batch_feats = [None] * len(batch)
        feats.extend(batch_feats)
    return feats

def analyze_playlist(sp, metrics: ApiMetrics, playlist_ref: str, outdir: Path, market: str):
    pid, pname = extract_playlist_id_or_name(playlist_ref)
    if not pid and pname:
        resolved_id, resolved_name = resolve_playlist_id_from_name(sp, metrics, pname, market)
        if not resolved_id:
            print(f"[WARN] Could not resolve playlist by name '{pname}' in market={market}", file=sys.stderr)
            return None
        pid = resolved_id
        pname = resolved_name

    # Try to fetch playlist with market param
    pl = api_call_with_retries(sp.playlist, metrics, f"playlist {pid}", pid, market=market)
    if pl is None:
        return None
    name = pl["name"]
    tracks = fetch_all_playlist_tracks(sp, metrics, pid, market=market)
    if not tracks:
        print(f"[WARN] No tracks found for playlist {name} ({pid}) in market={market}", file=sys.stderr)
        return None

    ids = [t["id"] for t in tracks if t.get("id")]
    feats = fetch_audio_features(sp, metrics, ids)

    rows = []
    for t, f in zip(tracks, feats):
        row = {
            "playlist_id": pid,
            "playlist_name": name,
            "track_id": t["id"],
            "track_name": t["name"],
            "artist": ", ".join(a["name"] for a in t.get("artists", [])),
            "album": t.get("album", {}).get("name"),
            "duration_ms": t.get("duration_ms"),
            "popularity": t.get("popularity"),
            "spotify_url": t.get("external_urls", {}).get("spotify"),
            "market": market,
        }
        if f:
            for c in AUDIO_FEAT_COLS:
                row[c] = f.get(c)
        rows.append(row)

    df = pd.DataFrame(rows)
    safe_name = "".join(ch for ch in name if ch.isalnum() or ch in (" ","-","_")).strip().replace(" ","_")
    outdir.mkdir(parents=True, exist_ok=True)
    raw_path = outdir / f"playlist_{safe_name}_{pid}_{market}.csv"
    df.to_csv(raw_path, index=False)

    num_cols = [c for c in AUDIO_FEAT_COLS if c in df.columns]
    agg = (
        df[num_cols]
        .apply(pd.to_numeric, errors="coerce")
        .describe()
        .loc[["mean","std","min","25%","50%","75%","max"]]
    )
    agg.insert(0, "playlist_name", name)
    agg.insert(1, "playlist_id", pid)
    agg.insert(2, "market", market)
    agg.reset_index(inplace=True)
    agg.rename(columns={"index":"stat"}, inplace=True)
    agg_path = outdir / f"playlist_{safe_name}_{pid}_{market}_stats.csv"
    agg.to_csv(agg_path, index=False)
    return str(raw_path), str(agg_path), name, pid, safe_name

def run_for_markets(playlists, outdir: Path, markets, use_client_credentials: bool, summary_path: Optional[Path] = None):
    # prefer CC for public playlists
    sp = get_spotify_client(use_client_credentials=use_client_credentials)
    metrics = ApiMetrics()
    all_stats = []
    created = []
    pids_names = []  # (safe_name, pid)
    processed = 0
    skipped_playlists = 0
    failures = 0
    for pl in playlists:
        for m in markets:
            try:
                result = analyze_playlist(sp, metrics, pl, outdir, market=m)
                if result is None:
                    skipped_playlists += 1
                    continue
                raw, stats, name, pid, safe_name = result
                pids_names.append((safe_name, pid))
                created.append(raw); created.append(stats)
                s = pd.read_csv(stats); s.insert(0, "source", name); all_stats.append(s)
                print(f"OK: {name} ({pid}) [{m}]")
                processed += 1
            except SpotifyException as se:
                failures += 1
                print(f"ERROR for {pl} [{m}]: {se}", file=sys.stderr)
            except Exception as e:
                failures += 1
                print(f"ERROR for {pl} [{m}]: {e}", file=sys.stderr)

    if all_stats:
        summary = pd.concat(all_stats, ignore_index=True)
        if summary_path is None:
            target_summary_path = outdir / f"summary_stats_{'_'.join(markets)}.csv"
        else:
            target_summary_path = Path(summary_path)
        target_summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary.to_csv(target_summary_path, index=False)
        created.append(str(target_summary_path))
        print(f"Wrote summary: {target_summary_path}")

    print(
        f"[SUMMARY] Processed {processed} playlist-market combinations, skipped {metrics.skipped_404} due to 404 "
        f"(total skipped {skipped_playlists}), retried {metrics.retries_429} times on 429, other failures {failures}.",
        file=sys.stderr,
    )

    return created, sorted(set(pids_names))

def merge_markets(outdir: Path, safe_name: str, pid: str, markets):
    dfs = []
    for m in markets:
        fp = outdir / f"playlist_{safe_name}_{pid}_{m}.csv"
        if fp.exists():
            dfs.append(pd.read_csv(fp))
    if not dfs:
        return None, None
    merged = pd.concat(dfs, ignore_index=True).drop_duplicates(subset=["track_id"])
    merged_path = outdir / f"playlist_{safe_name}_{pid}_MERGED.csv"
    merged.to_csv(merged_path, index=False)

    num_cols = [c for c in AUDIO_FEAT_COLS if c in merged.columns]
    agg = (
        merged[num_cols]
        .apply(pd.to_numeric, errors="coerce")
        .describe()
        .loc[["mean","std","min","25%","50%","75%","max"]]
    )
    agg.insert(0, "playlist_name", merged["playlist_name"].iloc[0])
    agg.insert(1, "playlist_id", pid)
    agg.insert(2, "market", "MERGED")
    agg.reset_index(inplace=True)
    agg.rename(columns={"index":"stat"}, inplace=True)
    merged_stats_path = outdir / f"playlist_{safe_name}_{pid}_MERGED_stats.csv"
    agg.to_csv(merged_stats_path, index=False)
    return str(merged_path), str(merged_stats_path)

def menu_prompt() -> int:
    print("\nSelect an option:")
    print(" 1) Playlist DE only")
    print(" 2) Playlist US only")
    print(" 3) Playlist UK only")
    print(" 4) All Playlists (DE, US, UK)")
    print(" 5) All Playlists + Merged List")
    print(" 6) Exit")
    try:
        choice = int(input("> ").strip())
        return choice
    except Exception:
        return 6

def parse_args():
    ap = argparse.ArgumentParser(description="Spotify playlist feature harvester (multi-market)")
    ap.add_argument("--playlists", nargs="+", help="Playlist IDs, URLs, or names (default: built-in set)")
    ap.add_argument("--outdir", default="spotify_playlists", help="Output directory")
    ap.add_argument("--out", help="Summary CSV output path (optional)")
    ap.add_argument("--markets", nargs="+", choices=list(MARKETS.keys()),
                    help="Markets to fetch (e.g., DE US UK)")
    ap.add_argument("-DE", action="store_true", help="Shortcut: fetch DE only")
    ap.add_argument("-US", action="store_true", help="Shortcut: fetch US only")
    ap.add_argument("-UK", action="store_true", help="Shortcut: fetch UK only")
    ap.add_argument("-all", action="store_true", help="Shortcut: fetch DE+US+UK")
    ap.add_argument("-m", "--merge", action="store_true", help="After fetching multiple markets, create merged lists")
    ap.add_argument("--use-client-credentials", action="store_true",
                    help="Use client-credentials auth (recommended for public playlists)")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing --out file if set")
    ap.add_argument("--no-menu", action="store_true", help="Do not show menu if no flags provided")
    return ap.parse_args()

def main():
    args = parse_args()
    playlists = args.playlists or DEFAULT_PLAYLISTS
    outdir = Path(args.outdir)
    summary_out = Path(args.out).expanduser() if args.out else None

    if summary_out and summary_out.exists():
        if args.overwrite:
            print(f"[INFO] Overwriting existing output file: {summary_out}", file=sys.stderr)
        else:
            print(f"[ERROR] Output file already exists: {summary_out}. Use --overwrite to replace it.", file=sys.stderr)
            sys.exit(2)

    selected_markets = []
    if args.markets:
        selected_markets = [MARKETS[m] for m in args.markets]
    else:
        if args.DE: selected_markets = [MARKETS["DE"]]
        if args.US: selected_markets = [MARKETS["US"]]
        if args.UK: selected_markets = [MARKETS["UK"]]
        if args.all: selected_markets = [MARKETS["DE"], MARKETS["US"], MARKETS["UK"]]
    if not selected_markets and not args.no_menu:
        choice = menu_prompt()
        if choice == 1: selected_markets = [MARKETS["DE"]]
        elif choice == 2: selected_markets = [MARKETS["US"]]
        elif choice == 3: selected_markets = [MARKETS["UK"]]
        elif choice == 4: selected_markets = [MARKETS["DE"], MARKETS["US"], MARKETS["UK"]]
        elif choice == 5: selected_markets = [MARKETS["DE"], MARKETS["US"], MARKETS["UK"]]; args.merge = True
        else:
            print("Bye."); sys.exit(0)
    if not selected_markets:
        selected_markets = [MARKETS["DE"]]

    print(f"Playlists: {playlists}")
    print(f"Markets: {selected_markets}")
    auth_mode = "client-credentials" if args.use_client_credentials else "user-auth"
    print(f"[INFO] Auth mode: {auth_mode}", file=sys.stderr)
    created_files, pid_pairs = run_for_markets(
        playlists,
        outdir,
        selected_markets,
        use_client_credentials=args.use_client_credentials,
        summary_path=summary_out,
    )

    if args.merge and len(selected_markets) > 1:
        print("Merging markets per playlist…")
        merged_files = []
        for safe_name, pid in pid_pairs:
            mfiles = merge_markets(outdir, safe_name, pid, selected_markets)
            if mfiles[0]:
                merged_files.extend(list(mfiles))
                print(f"MERGED: {safe_name} ({pid})")
        if merged_files:
            print("Merged outputs:"); [print(" -", mf) for mf in merged_files]

if __name__ == "__main__":
    main()
