"""
download_previews.py
====================
Lädt die 30s-Preview-MP3s von Deezer herunter.

WICHTIG: Deezer Preview-URLs sind nur ~15 Minuten gültig!
Daher holt dieses Script die URLs frisch vor jedem Download.

Input: scouted_tracks.csv aus dem Scouting-Script
Output: Verzeichnis mit MP3-Dateien, benannt nach cluster_trackid.mp3

Autor: Claude Opus (für Andreas Vogelsang)
Datum: 2026-03-02
"""

import sys
import time
import json
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import re

import requests
import pandas as pd
from tqdm import tqdm

# ══════════════════════════════════════════════════════════════════════════════
# KONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_INPUT = "scout_results_deezer/scouted_tracks.csv"
DEFAULT_OUTPUT = "previews"
DEEZER_API = "https://api.deezer.com"
REQUEST_TIMEOUT = 15
MAX_WORKERS = 4       # Reduziert wegen API-Calls pro Download
RETRY_COUNT = 2
API_DELAY = 0.1       # Delay zwischen API-Calls


# ══════════════════════════════════════════════════════════════════════════════
# API-HELFER
# ══════════════════════════════════════════════════════════════════════════════

def extract_expiry_from_url(url: str) -> int | None:
    """Extrahiert den Expiry-Timestamp aus einer Deezer Preview-URL."""
    if not url:
        return None
    match = re.search(r'exp=(\d+)', url)
    if match:
        return int(match.group(1))
    return None


def is_url_expired(url: str, buffer_seconds: int = 60) -> bool:
    """
    Prüft ob eine Preview-URL abgelaufen ist.
    
    Args:
        url: Die Preview-URL
        buffer_seconds: Sicherheitspuffer (default: 60s)
    
    Returns:
        True wenn abgelaufen oder nicht prüfbar
    """
    expiry = extract_expiry_from_url(url)
    if expiry is None:
        return False  # Kein Expiry gefunden, versuchen wir es einfach
    
    now = int(time.time())
    return now >= (expiry - buffer_seconds)


def get_fresh_preview_url(track_id: int) -> tuple[str | None, int | None]:
    """
    Holt eine frische Preview-URL für einen Track.
    
    Returns:
        (url, expiry_timestamp) oder (None, None)
    """
    try:
        response = requests.get(
            f"{DEEZER_API}/track/{track_id}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            url = data.get("preview")
            expiry = extract_expiry_from_url(url) if url else None
            return url, expiry
        return None, None
    except:
        return None, None


# ══════════════════════════════════════════════════════════════════════════════
# DOWNLOAD-LOGIK
# ══════════════════════════════════════════════════════════════════════════════

def download_preview(track_id: int, cluster: str, output_dir: Path, shared_state: dict = None) -> tuple[int, bool, str]:
    """
    Holt frische URL und lädt Preview herunter.
    
    Args:
        track_id: Deezer Track-ID
        cluster: Cluster-Name für Dateinamen
        output_dir: Zielverzeichnis
        shared_state: Dict für gemeinsamen Zustand (z.B. batch_expiry)
    
    Returns:
        (track_id, success, message)
    """
    filename = f"{cluster}_{track_id}.mp3"
    filepath = output_dir / filename
    
    # Skip wenn bereits vorhanden und groß genug
    if filepath.exists() and filepath.stat().st_size > 50000:
        return (track_id, True, "skipped")
    
    # Frische URL holen
    time.sleep(API_DELAY)  # Rate limiting
    preview_url, expiry = get_fresh_preview_url(track_id)
    
    if not preview_url:
        return (track_id, False, "no preview url")
    
    # Expiry-Check
    if is_url_expired(preview_url):
        return (track_id, False, "url expired immediately")
    
    # Expiry für Batch tracken (optional)
    if shared_state is not None and expiry:
        if 'min_expiry' not in shared_state or expiry < shared_state['min_expiry']:
            shared_state['min_expiry'] = expiry
    
    # Download
    for attempt in range(RETRY_COUNT + 1):
        try:
            response = requests.get(preview_url, timeout=REQUEST_TIMEOUT, stream=True)
            
            if response.status_code == 200:
                with open(filepath, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                if filepath.stat().st_size < 10000:
                    filepath.unlink()
                    return (track_id, False, "file too small")
                
                return (track_id, True, "downloaded")
            
            elif response.status_code == 403:
                return (track_id, False, "403 forbidden")
            elif response.status_code == 404:
                return (track_id, False, "404 not found")
            else:
                if attempt < RETRY_COUNT:
                    time.sleep(1)
                    continue
                return (track_id, False, f"HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            if attempt < RETRY_COUNT:
                time.sleep(1)
                continue
            return (track_id, False, "timeout")
        except requests.exceptions.RequestException as e:
            if attempt < RETRY_COUNT:
                time.sleep(1)
                continue
            return (track_id, False, str(e)[:50])
    
    return (track_id, False, "max retries")


def download_batch(items: list[tuple[int, str]], output_dir: Path, max_workers: int) -> dict:
    """
    Lädt eine Batch von Previews herunter.
    
    Args:
        items: Liste von (track_id, cluster) Tupeln
        output_dir: Zielverzeichnis
        max_workers: Anzahl paralleler Downloads
    
    Returns:
        Stats-Dict
    """
    stats = {"success": 0, "failed": 0, "skipped": 0, "errors": []}
    shared_state = {}  # Für Expiry-Tracking
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(download_preview, tid, cluster, output_dir, shared_state): (tid, cluster)
            for tid, cluster in items
        }
        
        with tqdm(total=len(futures), desc="Downloading", unit="file") as pbar:
            for future in as_completed(futures):
                track_id, success, message = future.result()
                
                if success:
                    if message == "skipped":
                        stats["skipped"] += 1
                    else:
                        stats["success"] += 1
                else:
                    stats["failed"] += 1
                    stats["errors"].append((track_id, message))
                    
                    # Bei Expiry-Fehler: Warnung ausgeben
                    if "expired" in message:
                        remaining = len([f for f in futures if not f.done()])
                        if remaining > 10:  # Nur warnen wenn noch viele übrig
                            tqdm.write(f"\n⚠️  URL expired! {remaining} Tracks noch ausstehend.")
                            tqdm.write(f"    URLs sind nur ~15 Min gültig. Evtl. Batch-Größe reduzieren.\n")
                
                pbar.update(1)
    
    return stats


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Download Deezer Preview-MP3s für MERT-Training"
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help=f"Input CSV mit Track-IDs (default: {DEFAULT_INPUT})"
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output-Verzeichnis für MP3s (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=MAX_WORKERS,
        help=f"Parallele Downloads (default: {MAX_WORKERS})"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximale Anzahl Downloads (0 = alle)"
    )
    parser.add_argument(
        "--cluster",
        type=str,
        default=None,
        help="Nur bestimmten Cluster downloaden"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Zeige was heruntergeladen würde, ohne tatsächlich zu laden"
    )
    args = parser.parse_args()

    # Input laden
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Fehler: Input-Datei nicht gefunden: {input_path}")
        sys.exit(1)
    
    df = pd.read_csv(input_path)
    
    print(f"═══════════════════════════════════════════════════════════════════════════════")
    print(f"  DEEZER PREVIEW DOWNLOADER")
    print(f"  (holt frische URLs vor jedem Download)")
    print(f"═══════════════════════════════════════════════════════════════════════════════")
    print(f"  Input:   {input_path}")
    print(f"  Tracks:  {len(df)}")
    
    # Filter nach Cluster (optional)
    if args.cluster:
        df = df[df["cluster"] == args.cluster]
        print(f"  Filter:  cluster={args.cluster} → {len(df)} Tracks")
    
    # Limit (optional)
    if args.limit > 0:
        df = df.head(args.limit)
        print(f"  Limit:   {args.limit} Tracks")
    
    # Items vorbereiten: (track_id, cluster)
    items = list(zip(df["track_id"].astype(int), df["cluster"]))
    
    # Cluster-Verteilung anzeigen
    cluster_counts = df["cluster"].value_counts()
    print(f"\n  Cluster-Verteilung:")
    for cluster, count in cluster_counts.items():
        print(f"    {cluster:25} {count:>5}")
    
    if args.dry_run:
        print(f"\n  [DRY RUN] Keine Downloads durchgeführt.")
        return
    
    # Output-Verzeichnis erstellen
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n  Output:  {output_dir.absolute()}")
    
    # Bereits vorhandene zählen
    existing = len(list(output_dir.glob("*.mp3")))
    if existing > 0:
        print(f"  Bereits vorhanden: {existing} Dateien (werden übersprungen)")
    
    # Geschätzte Zeit
    est_time = len(items) * (API_DELAY + 0.5) / args.workers / 60
    print(f"\n  Geschätzte Zeit: ~{est_time:.0f} Minuten bei {args.workers} Workern")
    print(f"  (inkl. API-Calls für frische URLs)")
    
    # Downloads starten
    print(f"\n  Starte Downloads...\n")
    
    stats = download_batch(items, output_dir, args.workers)
    
    # Ergebnis
    print(f"\n{'─'*79}")
    print(f"  DOWNLOAD COMPLETE")
    print(f"{'─'*79}")
    print(f"  Erfolgreich:    {stats['success']:>5}")
    print(f"  Übersprungen:   {stats['skipped']:>5}  (bereits vorhanden)")
    print(f"  Fehlgeschlagen: {stats['failed']:>5}")
    
    if stats["errors"]:
        # Fehler gruppieren
        error_types = {}
        for track_id, message in stats["errors"]:
            error_types[message] = error_types.get(message, 0) + 1
        
        print(f"\n  Fehler-Zusammenfassung:")
        for error, count in sorted(error_types.items(), key=lambda x: -x[1]):
            print(f"    {error:30} {count:>5}")
    
    # Speicherplatz-Info
    total_size = sum(f.stat().st_size for f in output_dir.glob("*.mp3"))
    file_count = len(list(output_dir.glob("*.mp3")))
    print(f"\n  Speicherplatz: {total_size / (1024*1024):.1f} MB")
    print(f"  Dateien:       {file_count}")
    
    if file_count > 0:
        print(f"  Durchschnitt:  {total_size / file_count / 1024:.1f} KB pro Datei")


if __name__ == "__main__":
    main()
