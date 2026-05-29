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

import importlib.util
from pathlib import Path

_strings: dict[str, str] = {}
_locale: str = "EN"


def load(locale: str = "EN") -> None:
    """Load strings for the given locale code (e.g. 'EN', 'DE')."""
    global _strings, _locale
    _locale = locale
    try:
        strings_path = Path(__file__).parent / locale / "strings.py"
        spec = importlib.util.spec_from_file_location(
            f"spotilyzer.locale.{locale}.strings", strings_path
        )
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            _strings = getattr(module, "STRINGS", {})
        else:
            _strings = {}
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
