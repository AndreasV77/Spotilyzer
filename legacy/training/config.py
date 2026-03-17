"""
Pfad-Konfiguration für das Spotilyzer-Training.

Liest training/paths.env (falls vorhanden) und stellt Path-Objekte bereit.
CLI-Argumente der Trainings-Skripte überschreiben diese Werte immer.

Verwendung in Skripten:
    from config import PREVIEWS_DIR, EMBEDDINGS_DIR, TRACKS_CSV, MODELS_DIR, SCOUT_DIR
    DEFAULT_INPUT = str(PREVIEWS_DIR)
"""

from pathlib import Path

_TRAINING_DIR = Path(__file__).parent
_PROJECT_ROOT = _TRAINING_DIR.parent
_ENV_FILE = _TRAINING_DIR / "paths.env"          # gitignored, lokal
_ENV_EXAMPLE = _TRAINING_DIR / "paths.env.example"  # committed, Vorlage


def _load_env() -> dict[str, str]:
    """Liest paths.env und gibt Key→Value-Dict zurück. Ignoriert Kommentare."""
    if not _ENV_FILE.exists():
        return {}
    result: dict[str, str] = {}
    for raw in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if key:
                result[key] = val
    return result


def _resolve(env: dict[str, str], key: str, default_relative: str) -> Path:
    """Gibt konfigurierten Pfad als absolutes Path-Objekt zurück.

    Reihenfolge:
    1. Wert aus paths.env (absolut oder relativ zum Projektroot)
    2. Default: <Projektroot>/<default_relative>
    """
    val = env.get(key, "").strip()
    if val:
        p = Path(val)
        return p if p.is_absolute() else (_PROJECT_ROOT / p).resolve()
    return (_PROJECT_ROOT / default_relative).resolve()


_env = _load_env()

# ── Öffentliche Pfade ────────────────────────────────────────────────
PREVIEWS_DIR   = _resolve(_env, "SPOTILYZER_PREVIEWS_DIR",   "previews")
EMBEDDINGS_DIR = _resolve(_env, "SPOTILYZER_EMBEDDINGS_DIR", "embeddings")
TRACKS_CSV     = _resolve(_env, "SPOTILYZER_TRACKS_CSV",     "scout_results_deezer/scouted_tracks.csv")
SCOUT_DIR      = _resolve(_env, "SPOTILYZER_SCOUT_DIR",      "scout_results_deezer")
MODELS_DIR     = _resolve(_env, "SPOTILYZER_MODELS_DIR",     "models")


def print_paths() -> None:
    """Gibt aktive Pfade zur Übersicht aus (nützlich für Debugging)."""
    if _ENV_FILE.exists():
        src = f"paths.env ({_ENV_FILE})"
    else:
        src = f"Defaults (paths.env fehlt — Vorlage: {_ENV_EXAMPLE})"
    print(f"  Konfigurationsquelle: {src}")
    print(f"  PREVIEWS_DIR   = {PREVIEWS_DIR}")
    print(f"  EMBEDDINGS_DIR = {EMBEDDINGS_DIR}")
    print(f"  TRACKS_CSV     = {TRACKS_CSV}")
    print(f"  SCOUT_DIR      = {SCOUT_DIR}")
    print(f"  MODELS_DIR     = {MODELS_DIR}")


if __name__ == "__main__":
    print("Spotilyzer Training — aktive Pfade:")
    print_paths()
