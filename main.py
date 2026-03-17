"""
Spotilyzer - Entry Point (GUI)
===============================
Startet die PySide6-GUI-Anwendung.

Usage:
    python main.py
"""

import sys
from pathlib import Path

# Sicherstellen, dass das Projekt-Root im Python-Path liegt
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# .env laden (HF_TOKEN u. a.) — optional, kein Fehler wenn nicht vorhanden
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass  # python-dotenv nicht installiert — Umgebungsvariablen aus dem System nutzen


def main():
    """Startet die Spotilyzer GUI."""
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
    except ImportError:
        print("Fehler: PySide6 nicht installiert!")
        print("Installieren mit: pip install PySide6")
        sys.exit(1)

    from spotilyzer.gui.app import run_app

    sys.exit(run_app())


if __name__ == "__main__":
    main()
