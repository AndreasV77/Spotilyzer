"""Localization support for Spotilyzer.

Usage::

    from spotilyzer.locale import t
    label = t("toolbar.open")
    msg   = t("status.analyzing", file="track.mp3")

The default locale is English (EN). To switch locale at runtime::

    from spotilyzer.locale import load
    load("DE")  # once DE/strings.py exists

New locale folders follow the pattern ``spotilyzer/locale/<LANG>/strings.py``
where each file defines a ``STRINGS: dict[str, str]`` mapping.
"""
from __future__ import annotations

from pathlib import Path

_strings: dict[str, str] = {}
_locale: str = "EN"


def load(locale: str = "EN") -> None:
    """Load strings for the given locale code (e.g. 'EN', 'DE')."""
    global _strings, _locale
    _locale = locale
    try:
        strings_path = Path(__file__).parent / locale / "strings.py"
        ns: dict = {}
        exec(strings_path.read_text(encoding="utf-8"), ns)
        _strings = ns.get("STRINGS", {})
    except Exception:
        _strings = {}


def t(key: str, **kwargs) -> str:
    """Return the localized string for *key*.

    Falls back to *key* itself when no translation is found so the UI
    never shows an empty label.

    Format placeholders are supported::

        t("status.analyzed", count=5, hits=2)
        # → "5 tracks analyzed | 2 hits found"
    """
    template = _strings.get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template


# Load English on import so the module is ready before any widget is created.
load("EN")
