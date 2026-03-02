"""
scout_genre_clusters.py
=======================
Scouting-Script für die MERT-Embedding-Architektur.
Sammelt Tracks pro Genre-Cluster via Seed-Artists und Related Artists.

Workflow:
1. Für jeden Cluster: Seed-Artists → Top-Tracks holen
2. Related Artists der Seeds holen → deren Top-Tracks holen
3. preview_url und popularity erfassen
4. Report: Tracks pro Cluster, Popularity-Verteilung, Previews verfügbar

Hinweis: Spotify's /recommendations-API wurde 2024 für Apps ohne Extended Quota
abgeschaltet. Dieses Script nutzt stattdessen /artist-related-artists, was
denselben Effekt hat, aber transparenter ist.

Autor: Claude Opus (für Andreas Vogelsang)
Datum: 2026-03-02
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.exceptions import SpotifyException

# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER-DEFINITIONEN
# ══════════════════════════════════════════════════════════════════════════════
# Seed-Artists pro Cluster. Spotify-Artist-IDs oder Namen (werden aufgelöst).
# Mehr Seeds = breitere Abdeckung, aber auch mehr API-Calls.

CLUSTERS = {
    # ── METAL (7) ─────────────────────────────────────────────────────────────
    "extreme_metal": {
        "display_name": "Extreme Metal",
        "description": "Death Metal, Melodic Death Metal, Thrash-Grenzbereich",
        "seed_artists": [
            "Arch Enemy", "Children of Bodom", "In Flames", "At The Gates",
            "Dismember", "Bloodbath", "Amon Amarth", "Dark Tranquillity",
            "Carcass", "Cannibal Corpse"
        ],
    },
    "gothic": {
        "display_name": "Gothic (M'era-Luna-Spektrum)",
        "description": "Gothic Metal/Rock/Doom, EBM, Aggrotech, NDH, Dark Electro",
        "seed_artists": [
            "Rammstein", "Eisbrecher", "Oomph!", "Megaherz",
            "Crematory", "HIM", "Lacrimosa", "Tiamat",
            "Combichrist", "Hocico", "Suicide Commando",
            "Die Krupps", "Front 242", "KMFDM",
            "Marilyn Manson", "Joachim Witt", "Unheilig"
        ],
    },
    "heavy_metal": {
        "display_name": "Heavy Metal / Classic Metal",
        "description": "Iron Maiden, Manowar, Judas Priest",
        "seed_artists": [
            "Iron Maiden", "Manowar", "Judas Priest", "Accept",
            "Saxon", "Dio", "Black Sabbath", "Ozzy Osbourne"
        ],
    },
    "power_symphonic": {
        "display_name": "Power Metal / Symphonic Metal",
        "description": "Dragonforce, Hammerfall, Powerwolf, Nightwish",
        "seed_artists": [
            "Dragonforce", "Hammerfall", "Powerwolf", "Sabaton",
            "Nightwish", "Epica", "Within Temptation", "Kamelot",
            "Blind Guardian", "Helloween"
        ],
    },
    "modern_metal": {
        "display_name": "Modern Metal",
        "description": "Five Finger Death Punch, Disturbed, etc.",
        "seed_artists": [
            "Five Finger Death Punch", "Disturbed", "Shinedown",
            "Breaking Benjamin", "Three Days Grace", "Seether",
            "Papa Roach", "Volbeat"
        ],
    },
    "metalcore": {
        "display_name": "Metalcore",
        "description": "As I Lay Dying, Killswitch Engage, Parkway Drive",
        "seed_artists": [
            "As I Lay Dying", "Killswitch Engage", "Parkway Drive",
            "August Burns Red", "Trivium", "Bullet for My Valentine",
            "Asking Alexandria", "We Came As Romans"
        ],
    },
    "crossover": {
        "display_name": "Crossover",
        "description": "Clawfinger, RATM, Body Count",
        "seed_artists": [
            "Rage Against The Machine", "Clawfinger", "Body Count",
            "Suicidal Tendencies", "Infectious Grooves", "Biohazard"
        ],
    },

    # ── ROCK (5) ──────────────────────────────────────────────────────────────
    "hard_rock": {
        "display_name": "Hard Rock",
        "description": "Airbourne, Bullet, Mötley Crüe",
        "seed_artists": [
            "Airbourne", "Bullet", "Mötley Crüe", "AC/DC",
            "Guns N' Roses", "Skid Row", "Def Leppard", "Bon Jovi"
        ],
    },
    "mainstream_rock": {
        "display_name": "Mainstream Rock",
        "description": "Bryan Adams, U2, Bon Jovi",
        "seed_artists": [
            "Bryan Adams", "U2", "Bon Jovi", "Nickelback",
            "Daughtry", "Matchbox Twenty", "Train", "OneRepublic"
        ],
    },
    "modern_rock": {
        "display_name": "Modern Rock",
        "description": "Godsmack, Saliva, Staind",
        "seed_artists": [
            "Godsmack", "Saliva", "Staind", "Puddle of Mudd",
            "Drowning Pool", "Theory of a Deadman", "Chevelle"
        ],
    },
    "classic_southern_rock": {
        "display_name": "Classic Rock / Southern Rock",
        "description": "Greta Van Fleet, Lynyrd Skynyrd, Deep Purple",
        "seed_artists": [
            "Greta Van Fleet", "Lynyrd Skynyrd", "Deep Purple",
            "Led Zeppelin", "The Allman Brothers Band", "ZZ Top",
            "Creedence Clearwater Revival", "Free"
        ],
    },
    "alternative_rock": {
        "display_name": "Alternative Rock",
        "description": "Smashing Pumpkins, Queens of the Stone Age",
        "seed_artists": [
            "The Smashing Pumpkins", "Queens of the Stone Age",
            "Foo Fighters", "Soundgarden", "Alice In Chains",
            "Pearl Jam", "Stone Temple Pilots", "Audioslave"
        ],
    },

    # ── PUNK / HARDCORE (2) ───────────────────────────────────────────────────
    "punk": {
        "display_name": "Punk",
        "description": "Green Day, Authority Zero, NOFX",
        "seed_artists": [
            "Green Day", "NOFX", "Bad Religion", "The Offspring",
            "Rancid", "Pennywise", "Rise Against", "Sum 41",
            "Authority Zero", "Anti-Flag"
        ],
    },
    "hardcore": {
        "display_name": "Hardcore",
        "description": "Biohazard, Hatebreed, Madball",
        "seed_artists": [
            "Hatebreed", "Madball", "Terror", "Agnostic Front",
            "Sick of It All", "Earth Crisis", "Converge"
        ],
    },

    # ── ELECTRONIC (2) ────────────────────────────────────────────────────────
    "trance": {
        "display_name": "Trance",
        "description": "Tiësto, Armin van Buuren, Above & Beyond",
        "seed_artists": [
            "Tiësto", "Armin van Buuren", "Above & Beyond",
            "Paul van Dyk", "Ferry Corsten", "ATB", "Dash Berlin"
        ],
    },
    "house": {
        "display_name": "House / Deep House / Lounge",
        "description": "Daft Punk, Disclosure, Calvin Harris",
        "seed_artists": [
            "Daft Punk", "Disclosure", "Calvin Harris",
            "David Guetta", "Kygo", "Robin Schulz", "Duke Dumont",
            "Rüfüs Du Sol", "Lane 8"
        ],
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# KONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# Popularity-Schwellen für Hit/Mid/Flop
POP_THRESHOLDS = {"flop": 35, "mid": 65}  # <35 = Flop, 35-65 = Mid, >65 = Hit

# Märkte
MARKETS = ["DE", "US", "GB"]

# API-Limits
TRACKS_PER_ARTIST = 10      # Top-Tracks pro Artist (Spotify-Maximum)
RELATED_ARTISTS_LIMIT = 5   # Wie viele Related Artists pro Seed-Artist
REQUEST_DELAY = 0.05        # Sekunden zwischen API-Calls
MAX_RETRIES = 3

# ══════════════════════════════════════════════════════════════════════════════
# DATENSTRUKTUREN
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TrackInfo:
    track_id: str
    track_name: str
    artist: str
    artist_id: str
    album: str
    popularity: int
    preview_url: Optional[str]
    duration_ms: int
    spotify_url: str
    cluster: str
    source: str  # "seed_artist" oder "related_artist"


@dataclass
class ClusterStats:
    cluster_id: str
    display_name: str
    total_tracks: int = 0
    unique_tracks: int = 0
    with_preview: int = 0
    without_preview: int = 0
    hits: int = 0
    mids: int = 0
    flops: int = 0
    seed_artists_found: int = 0
    seed_artists_not_found: list = field(default_factory=list)
    related_artists_found: int = 0
    total_artists: int = 0


# ══════════════════════════════════════════════════════════════════════════════
# API-HELFER
# ══════════════════════════════════════════════════════════════════════════════

def get_spotify_client(use_client_credentials: bool = False):
    """
    Initialisiert Spotify-Client.
    
    Args:
        use_client_credentials: Falls True, nutze App-Auth (kein User-Login).
                                Falls False, nutze OAuth mit User-Login.
    """
    load_dotenv()
    
    if use_client_credentials:
        return spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=os.getenv("SPOTIPY_CLIENT_ID"),
                client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
            )
        )
    
    # OAuth mit User-Login (öffnet Browser beim ersten Mal)
    from spotipy.oauth2 import SpotifyOAuth
    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=os.getenv("SPOTIPY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback"),
            scope="user-read-private",
            open_browser=True,
        )
    )


def api_call(fn, *args, **kwargs):
    """API-Call mit Retry-Logik für Rate-Limiting."""
    for attempt in range(MAX_RETRIES):
        try:
            result = fn(*args, **kwargs)
            time.sleep(REQUEST_DELAY)
            return result
        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = float(e.headers.get("Retry-After", 1.0))
                print(f"  [429] Rate limited, waiting {retry_after}s...", file=sys.stderr)
                time.sleep(retry_after)
                continue
            if e.http_status == 404:
                print(f"  [404] Not found: {e}", file=sys.stderr)
                return None
            raise
    return None


def resolve_artist_id(sp, artist_name: str) -> tuple[Optional[str], Optional[str]]:
    """
    Löst Artist-Namen zu Spotify-ID auf.
    
    Returns:
        Tuple von (artist_id, artist_name_from_spotify) oder (None, None)
    """
    result = api_call(sp.search, q=f'artist:"{artist_name}"', type="artist", limit=1)
    if result and result.get("artists", {}).get("items"):
        artist = result["artists"]["items"][0]
        return artist["id"], artist["name"]
    # Fallback ohne Quotes
    result = api_call(sp.search, q=artist_name, type="artist", limit=1)
    if result and result.get("artists", {}).get("items"):
        artist = result["artists"]["items"][0]
        return artist["id"], artist["name"]
    return None, None


# ══════════════════════════════════════════════════════════════════════════════
# TRACK-SAMMLUNG
# ══════════════════════════════════════════════════════════════════════════════

def extract_track_info(track: dict, cluster: str, source: str) -> Optional[TrackInfo]:
    """Extrahiert relevante Felder aus Spotify-Track-Objekt."""
    if not track or not track.get("id"):
        return None
    
    artists = track.get("artists", [])
    primary_artist_id = artists[0]["id"] if artists else ""
    
    return TrackInfo(
        track_id=track["id"],
        track_name=track.get("name", ""),
        artist=", ".join(a["name"] for a in artists),
        artist_id=primary_artist_id,
        album=track.get("album", {}).get("name", ""),
        popularity=track.get("popularity", 0),
        preview_url=track.get("preview_url"),
        duration_ms=track.get("duration_ms", 0),
        spotify_url=track.get("external_urls", {}).get("spotify", ""),
        cluster=cluster,
        source=source,
    )


def get_artist_top_tracks(sp, artist_id: str, market: str) -> list[dict]:
    """Holt Top-Tracks eines Artists."""
    result = api_call(sp.artist_top_tracks, artist_id, country=market)
    if result:
        return result.get("tracks", [])[:TRACKS_PER_ARTIST]
    return []


def get_related_artists(sp, artist_id: str, limit: int = RELATED_ARTISTS_LIMIT) -> list[dict]:
    """Holt Related Artists."""
    result = api_call(sp.artist_related_artists, artist_id)
    if result:
        return result.get("artists", [])[:limit]
    return []


def collect_tracks_for_cluster(
    sp, 
    cluster_id: str, 
    cluster_def: dict, 
    market: str,
    expand_related: bool = True
) -> tuple[list[TrackInfo], ClusterStats]:
    """
    Sammelt Tracks für einen Cluster via Seed-Artists und deren Related Artists.
    
    Args:
        sp: Spotify-Client
        cluster_id: Cluster-Key
        cluster_def: Cluster-Definition aus CLUSTERS
        market: Spotify-Markt (DE, US, GB, etc.)
        expand_related: Falls True, hole auch Tracks von Related Artists
    """
    stats = ClusterStats(
        cluster_id=cluster_id,
        display_name=cluster_def["display_name"],
    )
    tracks = []
    seen_track_ids = set()
    seen_artist_ids = set()

    seed_artists = cluster_def.get("seed_artists", [])
    print(f"\n  Cluster: {cluster_def['display_name']} ({len(seed_artists)} Seed-Artists)")

    # Phase 1: Seed-Artists
    resolved_seeds = []
    for artist_name in seed_artists:
        artist_id, resolved_name = resolve_artist_id(sp, artist_name)
        if not artist_id:
            print(f"    ⚠ Seed-Artist nicht gefunden: {artist_name}")
            stats.seed_artists_not_found.append(artist_name)
            continue

        stats.seed_artists_found += 1
        resolved_seeds.append((artist_id, resolved_name))
        seen_artist_ids.add(artist_id)

        # Top-Tracks des Seed-Artists
        top_tracks = get_artist_top_tracks(sp, artist_id, market)
        for t in top_tracks:
            info = extract_track_info(t, cluster_id, "seed_artist")
            if info and info.track_id not in seen_track_ids:
                tracks.append(info)
                seen_track_ids.add(info.track_id)

    print(f"    ✓ {stats.seed_artists_found} Seed-Artists → {len(tracks)} Tracks")

    # Phase 2: Related Artists (falls aktiviert)
    if expand_related:
        related_tracks_before = len(tracks)
        
        for seed_id, seed_name in resolved_seeds:
            related = get_related_artists(sp, seed_id, limit=RELATED_ARTISTS_LIMIT)
            
            for rel_artist in related:
                rel_id = rel_artist.get("id")
                if not rel_id or rel_id in seen_artist_ids:
                    continue
                
                seen_artist_ids.add(rel_id)
                stats.related_artists_found += 1
                
                # Top-Tracks des Related Artists
                top_tracks = get_artist_top_tracks(sp, rel_id, market)
                for t in top_tracks:
                    info = extract_track_info(t, cluster_id, "related_artist")
                    if info and info.track_id not in seen_track_ids:
                        tracks.append(info)
                        seen_track_ids.add(info.track_id)

        related_tracks_added = len(tracks) - related_tracks_before
        print(f"    ✓ {stats.related_artists_found} Related Artists → +{related_tracks_added} Tracks")

    # Statistiken berechnen
    stats.total_artists = len(seen_artist_ids)
    stats.total_tracks = len(tracks)
    stats.unique_tracks = len(seen_track_ids)
    stats.with_preview = sum(1 for t in tracks if t.preview_url)
    stats.without_preview = stats.unique_tracks - stats.with_preview
    stats.hits = sum(1 for t in tracks if t.popularity > POP_THRESHOLDS["mid"])
    stats.mids = sum(1 for t in tracks if POP_THRESHOLDS["flop"] <= t.popularity <= POP_THRESHOLDS["mid"])
    stats.flops = sum(1 for t in tracks if t.popularity < POP_THRESHOLDS["flop"])

    return tracks, stats


# ══════════════════════════════════════════════════════════════════════════════
# REPORTING
# ══════════════════════════════════════════════════════════════════════════════

def print_cluster_report(stats: ClusterStats):
    """Gibt Cluster-Statistiken formatiert aus."""
    viability = "✅" if stats.with_preview >= 300 else "⚠️" if stats.with_preview >= 100 else "❌"

    print(f"""
    ┌─────────────────────────────────────────────────────────────
    │ {stats.display_name}
    ├─────────────────────────────────────────────────────────────
    │ Artists:           {stats.total_artists:>6}  (Seeds: {stats.seed_artists_found}, Related: {stats.related_artists_found})
    │ Tracks gesamt:     {stats.unique_tracks:>6}
    │ Mit Preview:       {stats.with_preview:>6}  {viability}
    │ Ohne Preview:      {stats.without_preview:>6}
    ├─────────────────────────────────────────────────────────────
    │ Hit (>{POP_THRESHOLDS['mid']}):       {stats.hits:>6}  ({100*stats.hits/max(1,stats.unique_tracks):.1f}%)
    │ Mid ({POP_THRESHOLDS['flop']}-{POP_THRESHOLDS['mid']}):      {stats.mids:>6}  ({100*stats.mids/max(1,stats.unique_tracks):.1f}%)
    │ Flop (<{POP_THRESHOLDS['flop']}):       {stats.flops:>6}  ({100*stats.flops/max(1,stats.unique_tracks):.1f}%)
    ├─────────────────────────────────────────────────────────────
    │ Seeds nicht gefunden: {len(stats.seed_artists_not_found):>3}  {', '.join(stats.seed_artists_not_found[:3]) + ('...' if len(stats.seed_artists_not_found) > 3 else '') if stats.seed_artists_not_found else '-'}
    └─────────────────────────────────────────────────────────────""")


def print_summary(all_stats: list[ClusterStats]):
    """Gibt Gesamtzusammenfassung aus."""
    total_tracks = sum(s.unique_tracks for s in all_stats)
    total_previews = sum(s.with_preview for s in all_stats)
    total_artists = sum(s.total_artists for s in all_stats)
    viable = [s for s in all_stats if s.with_preview >= 300]
    marginal = [s for s in all_stats if 100 <= s.with_preview < 300]
    insufficient = [s for s in all_stats if s.with_preview < 100]

    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════
║  SCOUTING SUMMARY
╠═══════════════════════════════════════════════════════════════════════════════
║  Cluster gesamt:           {len(all_stats):>5}
║  Artists gesamt:           {total_artists:>5}
║  Tracks gesamt:            {total_tracks:>5}
║  Mit Preview:              {total_previews:>5}  ({100*total_previews/max(1,total_tracks):.1f}%)
╠═══════════════════════════════════════════════════════════════════════════════
║  ✅ Trainierbar (≥300):    {len(viable):>5}  {', '.join(s.cluster_id for s in viable) if viable else '-'}
║  ⚠️  Grenzwertig (100-299): {len(marginal):>5}  {', '.join(s.cluster_id for s in marginal) if marginal else '-'}
║  ❌ Unzureichend (<100):   {len(insufficient):>5}  {', '.join(s.cluster_id for s in insufficient) if insufficient else '-'}
╚═══════════════════════════════════════════════════════════════════════════════
""")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Scouting-Script für Spotilyzer Genre-Cluster (via Related Artists)"
    )
    parser.add_argument(
        "--clusters",
        nargs="+",
        choices=list(CLUSTERS.keys()) + ["all"],
        default=["all"],
        help="Cluster zum Scouten (default: all)"
    )
    parser.add_argument(
        "--markets",
        nargs="+",
        default=["DE"],
        help="Märkte (default: DE)"
    )
    parser.add_argument(
        "--outdir",
        default="scout_results",
        help="Output-Verzeichnis (default: scout_results)"
    )
    parser.add_argument(
        "--save-tracks",
        action="store_true",
        help="Speichere Track-Listen als CSV (für späteres Training)"
    )
    parser.add_argument(
        "--no-related",
        action="store_true",
        help="Keine Related Artists abfragen (nur Seed-Artists)"
    )
    parser.add_argument(
        "--related-depth",
        type=int,
        default=RELATED_ARTISTS_LIMIT,
        help=f"Anzahl Related Artists pro Seed (default: {RELATED_ARTISTS_LIMIT})"
    )
    parser.add_argument(
        "--client-credentials",
        action="store_true",
        help="Nutze Client Credentials Auth (ohne User-Login). Falls Fehler 403, ohne diesen Flag versuchen."
    )
    args = parser.parse_args()

    # Globale Konfiguration anpassen
    global RELATED_ARTISTS_LIMIT
    RELATED_ARTISTS_LIMIT = args.related_depth

    # Cluster-Auswahl
    if "all" in args.clusters:
        selected_clusters = list(CLUSTERS.keys())
    else:
        selected_clusters = args.clusters

    # Setup
    sp = get_spotify_client(use_client_credentials=args.client_credentials)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    all_stats = []
    all_tracks = []

    print(f"═══════════════════════════════════════════════════════════════════════════════")
    print(f"  SPOTILYZER GENRE SCOUTING (via Related Artists)")
    print(f"  Cluster: {len(selected_clusters)} | Märkte: {', '.join(args.markets)}")
    print(f"  Related Artists pro Seed: {RELATED_ARTISTS_LIMIT if not args.no_related else 'deaktiviert'}")
    print(f"═══════════════════════════════════════════════════════════════════════════════")

    for market in args.markets:
        print(f"\n▶ Markt: {market}")
        print(f"───────────────────────────────────────────────────────────────────────────────")

        for cluster_id in selected_clusters:
            cluster_def = CLUSTERS[cluster_id]
            tracks, stats = collect_tracks_for_cluster(
                sp, 
                cluster_id, 
                cluster_def, 
                market,
                expand_related=not args.no_related
            )

            all_stats.append(stats)
            all_tracks.extend(tracks)

            print_cluster_report(stats)

    # Summary
    print_summary(all_stats)

    # Speichern
    if args.save_tracks and all_tracks:
        # Tracks als CSV
        df = pd.DataFrame([asdict(t) for t in all_tracks])
        tracks_path = outdir / f"scouted_tracks_{'_'.join(args.markets)}.csv"
        df.to_csv(tracks_path, index=False)
        print(f"Tracks gespeichert: {tracks_path}")

        # Stats als JSON
        stats_path = outdir / f"scouting_stats_{'_'.join(args.markets)}.json"
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump([asdict(s) for s in all_stats], f, indent=2, ensure_ascii=False)
        print(f"Stats gespeichert: {stats_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
