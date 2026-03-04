"""
scout_genre_clusters_deezer.py
==============================
Scouting-Script für die MERT-Embedding-Architektur.
Nutzt die Deezer API (kostenlos, ohne Auth) statt Spotify.

Vorteile gegenüber Spotify:
- Keine API-Registrierung nötig
- Preview-URLs funktionieren (auch in DE)
- "rank" als Popularity-Proxy verfügbar
- Artist Top Tracks verfügbar

Workflow:
1. Für jeden Cluster: Seed-Artists suchen → Top-Tracks holen
2. preview_url und rank erfassen
3. Report: Tracks pro Cluster, Rank-Verteilung, Previews verfügbar

Autor: Claude Opus (für Andreas Vogelsang)
Datum: 2026-03-02
"""

import sys
import time
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from urllib.parse import quote

import requests
import pandas as pd

# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER-DEFINITIONEN
# ══════════════════════════════════════════════════════════════════════════════

CLUSTERS = {
    # ── METAL (7) ─────────────────────────────────────────────────────────────
    "extreme_metal": {
        "display_name": "Extreme Metal",
        "description": "Death Metal, Melodic Death Metal, Thrash-Grenzbereich",
        "seed_artists": [
            "Arch Enemy", "Children of Bodom", "In Flames", "At The Gates",
            "Dismember", "Bloodbath", "Amon Amarth", "Dark Tranquillity",
            "Carcass", "Cannibal Corpse", "Kreator", "Sodom", "Destruction"
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
            "Saxon", "Dio", "Black Sabbath", "Ozzy Osbourne",
            "Motörhead", "Scorpions", "W.A.S.P."
        ],
    },
    "power_symphonic": {
        "display_name": "Power Metal / Symphonic Metal",
        "description": "Dragonforce, Hammerfall, Powerwolf, Nightwish",
        "seed_artists": [
            "Dragonforce", "Hammerfall", "Powerwolf", "Sabaton",
            "Nightwish", "Epica", "Within Temptation", "Kamelot",
            "Blind Guardian", "Helloween", "Stratovarius", "Sonata Arctica"
        ],
    },
    "modern_metal": {
        "display_name": "Modern Metal",
        "description": "Five Finger Death Punch, Disturbed, etc.",
        "seed_artists": [
            "Five Finger Death Punch", "Disturbed", "Shinedown",
            "Breaking Benjamin", "Three Days Grace", "Seether",
            "Papa Roach", "Volbeat", "Avenged Sevenfold", "Bullet For My Valentine"
        ],
    },
    "metalcore": {
        "display_name": "Metalcore",
        "description": "As I Lay Dying, Killswitch Engage, Parkway Drive",
        "seed_artists": [
            "As I Lay Dying", "Killswitch Engage", "Parkway Drive",
            "August Burns Red", "Trivium", "Bullet for My Valentine",
            "Asking Alexandria", "We Came As Romans", "Architects", "Bring Me The Horizon"
        ],
    },
    "crossover": {
        "display_name": "Crossover",
        "description": "Clawfinger, RATM, Body Count",
        "seed_artists": [
            "Rage Against The Machine", "Clawfinger", "Body Count",
            "Suicidal Tendencies", "Infectious Grooves", "Dog Eat Dog",
            "Downset", "Stuck Mojo"
        ],
    },

    # ── ROCK (5) ──────────────────────────────────────────────────────────────
    "hard_rock": {
        "display_name": "Hard Rock",
        "description": "Airbourne, Bullet, Mötley Crüe",
        "seed_artists": [
            "Airbourne", "Bullet", "Mötley Crüe", "AC/DC",
            "Guns N' Roses", "Skid Row", "Def Leppard", "Bon Jovi",
            "Kiss", "Whitesnake", "Twisted Sister"
        ],
    },
    "mainstream_rock": {
        "display_name": "Mainstream Rock",
        "description": "Bryan Adams, U2, Bon Jovi",
        "seed_artists": [
            "Bryan Adams", "U2", "Bon Jovi", "Nickelback",
            "Daughtry", "Matchbox Twenty", "Train", "OneRepublic",
            "Coldplay", "The Script"
        ],
    },
    "modern_rock": {
        "display_name": "Modern Rock",
        "description": "Godsmack, Saliva, Staind",
        "seed_artists": [
            "Godsmack", "Saliva", "Staind", "Puddle of Mudd",
            "Drowning Pool", "Theory of a Deadman", "Chevelle",
            "Sevendust", "Trapt", "Evanescence"
        ],
    },
    "classic_southern_rock": {
        "display_name": "Classic Rock / Southern Rock",
        "description": "Greta Van Fleet, Lynyrd Skynyrd, Deep Purple",
        "seed_artists": [
            "Greta Van Fleet", "Lynyrd Skynyrd", "Deep Purple",
            "Led Zeppelin", "The Allman Brothers Band", "ZZ Top",
            "Creedence Clearwater Revival", "Free", "Bad Company", "Foghat"
        ],
    },
    "alternative_rock": {
        "display_name": "Alternative Rock",
        "description": "Smashing Pumpkins, Queens of the Stone Age",
        "seed_artists": [
            "The Smashing Pumpkins", "Queens of the Stone Age",
            "Foo Fighters", "Soundgarden", "Alice In Chains",
            "Pearl Jam", "Stone Temple Pilots", "Audioslave",
            "Nirvana", "Rage Against The Machine"
        ],
    },

    # ── PUNK / HARDCORE (2) ───────────────────────────────────────────────────
    "punk": {
        "display_name": "Punk",
        "description": "Green Day, Authority Zero, NOFX",
        "seed_artists": [
            "Green Day", "NOFX", "Bad Religion", "The Offspring",
            "Rancid", "Pennywise", "Rise Against", "Sum 41",
            "Authority Zero", "Anti-Flag", "Social Distortion", "Dropkick Murphys"
        ],
    },
    "hardcore": {
        "display_name": "Hardcore",
        "description": "Biohazard, Hatebreed, Madball",
        "seed_artists": [
            "Hatebreed", "Madball", "Terror", "Agnostic Front",
            "Sick of It All", "Earth Crisis", "Converge",
            "Knocked Loose", "Code Orange", "Turnstile"
        ],
    },

    # ── ELECTRONIC (2) ────────────────────────────────────────────────────────
    "trance": {
        "display_name": "Trance",
        "description": "Tiësto, Armin van Buuren, Above & Beyond",
        "seed_artists": [
            "Tiësto", "Armin van Buuren", "Above & Beyond",
            "Paul van Dyk", "Ferry Corsten", "ATB", "Dash Berlin",
            "Cosmic Gate", "Gareth Emery", "Andrew Rayel"
        ],
    },
    "house": {
        "display_name": "House / Deep House / Lounge",
        "description": "Daft Punk, Disclosure, Calvin Harris",
        "seed_artists": [
            "Daft Punk", "Disclosure", "Calvin Harris",
            "David Guetta", "Kygo", "Robin Schulz", "Duke Dumont",
            "Rüfüs Du Sol", "Lane 8", "Nora En Pure", "Meduza"
        ],
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# LÄNDER-TOPLISTEN (Deezer Playlist-IDs)
# ══════════════════════════════════════════════════════════════════════════════

COUNTRY_CHARTS = {
    "DE": {"name": "Germany", "playlist_id": 1111143121},
    "US": {"name": "USA", "playlist_id": 1313621735},
    "UK": {"name": "UK", "playlist_id": 1111142221},
    "FR": {"name": "France", "playlist_id": 1109890291},
    "JP": {"name": "Japan", "playlist_id": 1362508955},
    "BR": {"name": "Brazil", "playlist_id": 1111141961},
    "ES": {"name": "Spain", "playlist_id": 1116190041},
    # Globale Charts
    "GLOBAL": {"name": "Global", "playlist_id": 3155776842},
}

# ══════════════════════════════════════════════════════════════════════════════
# KONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# Rank-Schwellen für Hit/Mid/Flop (Deezer rank: höher = populärer, max ~1.000.000)
# Diese Werte sind geschätzt und sollten nach dem ersten Scouting kalibriert werden
RANK_THRESHOLDS = {"flop": 300000, "mid": 700000}  # <300k = Flop, 300k-700k = Mid, >700k = Hit

# API-Konfiguration
DEEZER_API_BASE = "https://api.deezer.com"
REQUEST_DELAY = 0.25  # Sekunden zwischen API-Calls (Deezer ist toleranter als Spotify)
MAX_RETRIES = 3
TRACKS_PER_ARTIST = 25  # Deezer liefert bis zu 50, wir nehmen 25

# ══════════════════════════════════════════════════════════════════════════════
# DATENSTRUKTUREN
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TrackInfo:
    track_id: int
    track_name: str
    artist: str
    artist_id: int
    album: str
    rank: int  # Deezer's popularity equivalent
    preview_url: Optional[str]
    duration_sec: int
    deezer_url: str
    cluster: str
    source: str  # "seed_artist" oder "chart"


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
    avg_rank: float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# API-HELFER
# ══════════════════════════════════════════════════════════════════════════════

def api_get(endpoint: str, params: dict = None) -> Optional[dict]:
    """
    Führt einen GET-Request gegen die Deezer API aus.
    Keine Authentifizierung nötig für öffentliche Endpoints.
    """
    url = f"{DEEZER_API_BASE}/{endpoint}"
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params, timeout=10)
            time.sleep(REQUEST_DELAY)
            
            if response.status_code == 200:
                data = response.json()
                # Deezer gibt Fehler im JSON zurück, nicht als HTTP-Status
                if "error" in data:
                    print(f"  [API Error] {data['error'].get('message', 'Unknown error')}", file=sys.stderr)
                    return None
                return data
            elif response.status_code == 429:
                print(f"  [429] Rate limited, waiting 5s...", file=sys.stderr)
                time.sleep(5)
                continue
            else:
                print(f"  [HTTP {response.status_code}] {url}", file=sys.stderr)
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"  [Request Error] {e}", file=sys.stderr)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)
                continue
            return None
    
    return None


def search_artist(artist_name: str) -> Optional[dict]:
    """Sucht einen Artist nach Namen und gibt den besten Match zurück."""
    data = api_get("search/artist", {"q": artist_name, "limit": 5})
    if not data or not data.get("data"):
        return None
    
    # Exakten Match bevorzugen (case-insensitive)
    for artist in data["data"]:
        if artist["name"].lower() == artist_name.lower():
            return artist
    
    # Sonst ersten Treffer nehmen
    return data["data"][0]


def get_artist_top_tracks(artist_id: int, limit: int = 25) -> list[dict]:
    """Holt die Top-Tracks eines Artists."""
    data = api_get(f"artist/{artist_id}/top", {"limit": limit})
    if not data or not data.get("data"):
        return []
    return data["data"]


def get_playlist_tracks(playlist_id: int, limit: int = 100) -> list[dict]:
    """Holt Tracks aus einer Playlist (z.B. Country Charts)."""
    data = api_get(f"playlist/{playlist_id}/tracks", {"limit": limit})
    if not data or not data.get("data"):
        return []
    return data["data"]


# ══════════════════════════════════════════════════════════════════════════════
# TRACK-SAMMLUNG
# ══════════════════════════════════════════════════════════════════════════════

def extract_track_info(track: dict, cluster: str, source: str) -> Optional[TrackInfo]:
    """Extrahiert relevante Felder aus Deezer-Track-Objekt."""
    if not track or not track.get("id"):
        return None
    
    artist = track.get("artist", {})
    
    return TrackInfo(
        track_id=track["id"],
        track_name=track.get("title", ""),
        artist=artist.get("name", "Unknown"),
        artist_id=artist.get("id", 0),
        album=track.get("album", {}).get("title", ""),
        rank=track.get("rank", 0),
        preview_url=track.get("preview"),
        duration_sec=track.get("duration", 0),
        deezer_url=track.get("link", ""),
        cluster=cluster,
        source=source,
    )


def collect_tracks_for_cluster(cluster_id: str, cluster_def: dict, tracks_per_artist: int = 25) -> tuple[list[TrackInfo], ClusterStats]:
    """Sammelt Tracks für einen Cluster via Seed-Artists."""
    stats = ClusterStats(
        cluster_id=cluster_id,
        display_name=cluster_def["display_name"],
    )
    tracks = []
    seen_track_ids = set()

    seed_artists = cluster_def.get("seed_artists", [])
    print(f"\n  Cluster: {cluster_def['display_name']} ({len(seed_artists)} Seed-Artists)")

    for artist_name in seed_artists:
        artist = search_artist(artist_name)
        if not artist:
            print(f"    ⚠ Artist nicht gefunden: {artist_name}")
            stats.seed_artists_not_found.append(artist_name)
            continue

        stats.seed_artists_found += 1

        # Top-Tracks des Artists
        top_tracks = get_artist_top_tracks(artist["id"], limit=tracks_per_artist)
        for t in top_tracks:
            info = extract_track_info(t, cluster_id, "seed_artist")
            if info and info.track_id not in seen_track_ids:
                tracks.append(info)
                seen_track_ids.add(info.track_id)

    print(f"    ✓ {stats.seed_artists_found} Artists → {len(tracks)} Tracks")

    # Statistiken berechnen
    stats.total_tracks = len(tracks)
    stats.unique_tracks = len(seen_track_ids)
    stats.with_preview = sum(1 for t in tracks if t.preview_url)
    stats.without_preview = stats.unique_tracks - stats.with_preview
    stats.hits = sum(1 for t in tracks if t.rank > RANK_THRESHOLDS["mid"])
    stats.mids = sum(1 for t in tracks if RANK_THRESHOLDS["flop"] <= t.rank <= RANK_THRESHOLDS["mid"])
    stats.flops = sum(1 for t in tracks if t.rank < RANK_THRESHOLDS["flop"])
    stats.avg_rank = sum(t.rank for t in tracks) / max(1, len(tracks))

    return tracks, stats


def collect_chart_tracks(country_code: str) -> tuple[list[TrackInfo], int]:
    """Sammelt Tracks aus einer Länder-Topliste."""
    if country_code not in COUNTRY_CHARTS:
        print(f"  ⚠ Unbekannter Country-Code: {country_code}")
        return [], 0
    
    chart = COUNTRY_CHARTS[country_code]
    print(f"\n  Chart: {chart['name']} (Playlist {chart['playlist_id']})")
    
    playlist_tracks = get_playlist_tracks(chart["playlist_id"])
    tracks = []
    
    for t in playlist_tracks:
        info = extract_track_info(t, f"chart_{country_code.lower()}", "chart")
        if info:
            tracks.append(info)
    
    with_preview = sum(1 for t in tracks if t.preview_url)
    print(f"    ✓ {len(tracks)} Tracks, {with_preview} mit Preview")
    
    return tracks, with_preview


# ══════════════════════════════════════════════════════════════════════════════
# REPORTING
# ══════════════════════════════════════════════════════════════════════════════

def print_cluster_report(stats: ClusterStats):
    """Gibt Cluster-Statistiken formatiert aus."""
    viability = "✅" if stats.with_preview >= 200 else "⚠️" if stats.with_preview >= 100 else "❌"

    print(f"""
    ┌─────────────────────────────────────────────────────────────
    │ {stats.display_name}
    ├─────────────────────────────────────────────────────────────
    │ Tracks gesamt:     {stats.unique_tracks:>6}
    │ Mit Preview:       {stats.with_preview:>6}  {viability}
    │ Ohne Preview:      {stats.without_preview:>6}
    │ Avg Rank:          {stats.avg_rank:>10,.0f}
    ├─────────────────────────────────────────────────────────────
    │ Hit (>{RANK_THRESHOLDS['mid']/1000:.0f}k):      {stats.hits:>6}  ({100*stats.hits/max(1,stats.unique_tracks):.1f}%)
    │ Mid ({RANK_THRESHOLDS['flop']/1000:.0f}k-{RANK_THRESHOLDS['mid']/1000:.0f}k):   {stats.mids:>6}  ({100*stats.mids/max(1,stats.unique_tracks):.1f}%)
    │ Flop (<{RANK_THRESHOLDS['flop']/1000:.0f}k):     {stats.flops:>6}  ({100*stats.flops/max(1,stats.unique_tracks):.1f}%)
    ├─────────────────────────────────────────────────────────────
    │ Seeds gefunden:    {stats.seed_artists_found:>6}
    │ Seeds fehlen:      {len(stats.seed_artists_not_found):>6}  {', '.join(stats.seed_artists_not_found[:3]) + ('...' if len(stats.seed_artists_not_found) > 3 else '') if stats.seed_artists_not_found else '-'}
    └─────────────────────────────────────────────────────────────""")


def print_summary(all_stats: list[ClusterStats], chart_tracks: int = 0):
    """Gibt Gesamtzusammenfassung aus."""
    total_tracks = sum(s.unique_tracks for s in all_stats) + chart_tracks
    total_previews = sum(s.with_preview for s in all_stats)
    viable = [s for s in all_stats if s.with_preview >= 200]
    marginal = [s for s in all_stats if 100 <= s.with_preview < 200]
    insufficient = [s for s in all_stats if s.with_preview < 100]

    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════
║  DEEZER SCOUTING SUMMARY
╠═══════════════════════════════════════════════════════════════════════════════
║  Cluster gesamt:           {len(all_stats):>5}
║  Tracks gesamt:            {total_tracks:>5}  (inkl. {chart_tracks} Chart-Tracks)
║  Mit Preview:              {total_previews:>5}  ({100*total_previews/max(1,total_tracks):.1f}%)
╠═══════════════════════════════════════════════════════════════════════════════
║  ✅ Trainierbar (≥200):    {len(viable):>5}  {', '.join(s.cluster_id for s in viable) if viable else '-'}
║  ⚠️  Grenzwertig (100-199): {len(marginal):>5}  {', '.join(s.cluster_id for s in marginal) if marginal else '-'}
║  ❌ Unzureichend (<100):   {len(insufficient):>5}  {', '.join(s.cluster_id for s in insufficient) if insufficient else '-'}
╚═══════════════════════════════════════════════════════════════════════════════
""")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Scouting-Script für Spotilyzer Genre-Cluster (Deezer API)"
    )
    parser.add_argument(
        "--clusters",
        nargs="+",
        choices=list(CLUSTERS.keys()) + ["all"],
        default=["all"],
        help="Cluster zum Scouten (default: all)"
    )
    parser.add_argument(
        "--charts",
        nargs="+",
        choices=list(COUNTRY_CHARTS.keys()) + ["none"],
        default=["none"],
        help="Länder-Charts einbeziehen (default: none)"
    )
    from config import SCOUT_DIR as _SCOUT_DIR
    parser.add_argument(
        "--outdir",
        default=str(_SCOUT_DIR),
        help=f"Output-Verzeichnis (default: {_SCOUT_DIR})"
    )
    parser.add_argument(
        "--save-tracks",
        action="store_true",
        help="Speichere Track-Listen als CSV (für späteres Training)"
    )
    parser.add_argument(
        "--tracks-per-artist",
        type=int,
        default=TRACKS_PER_ARTIST,
        help=f"Tracks pro Artist (default: {TRACKS_PER_ARTIST}, max: 50)"
    )
    args = parser.parse_args()

    # Tracks-per-Artist aus Argument (überschreibt Default, max 50)
    tracks_per_artist = min(50, args.tracks_per_artist)

    # Cluster-Auswahl
    if "all" in args.clusters:
        selected_clusters = list(CLUSTERS.keys())
    else:
        selected_clusters = args.clusters

    # Output-Verzeichnis
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    all_stats = []
    all_tracks = []
    chart_track_count = 0

    print(f"═══════════════════════════════════════════════════════════════════════════════")
    print(f"  SPOTILYZER GENRE SCOUTING (Deezer API)")
    print(f"  Cluster: {len(selected_clusters)} | Tracks/Artist: {tracks_per_artist}")
    print(f"  Charts: {', '.join(args.charts) if 'none' not in args.charts else 'keine'}")
    print(f"═══════════════════════════════════════════════════════════════════════════════")

    # Genre-Cluster scouten
    for cluster_id in selected_clusters:
        cluster_def = CLUSTERS[cluster_id]
        tracks, stats = collect_tracks_for_cluster(cluster_id, cluster_def, tracks_per_artist)

        all_stats.append(stats)
        all_tracks.extend(tracks)

        print_cluster_report(stats)

    # Länder-Charts scouten (optional)
    if "none" not in args.charts:
        print(f"\n{'─'*79}")
        print(f"  LÄNDER-CHARTS")
        print(f"{'─'*79}")
        
        for country in args.charts:
            chart_tracks, with_preview = collect_chart_tracks(country)
            all_tracks.extend(chart_tracks)
            chart_track_count += len(chart_tracks)

    # Summary
    print_summary(all_stats, chart_track_count)

    # Speichern
    if args.save_tracks and all_tracks:
        # Tracks als CSV
        df = pd.DataFrame([asdict(t) for t in all_tracks])
        tracks_path = outdir / "scouted_tracks.csv"
        df.to_csv(tracks_path, index=False)
        print(f"Tracks gespeichert: {tracks_path}")

        # Stats als JSON
        stats_path = outdir / "scouting_stats.json"
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump([asdict(s) for s in all_stats], f, indent=2, ensure_ascii=False)
        print(f"Stats gespeichert: {stats_path}")

        # Preview-Liste (für Download-Script)
        previews = [(t.track_id, t.preview_url, t.cluster) for t in all_tracks if t.preview_url]
        preview_path = outdir / "preview_urls.json"
        with open(preview_path, "w", encoding="utf-8") as f:
            json.dump(previews, f, indent=2)
        print(f"Preview-URLs gespeichert: {preview_path} ({len(previews)} URLs)")

    print("\nDone.")


if __name__ == "__main__":
    main()
