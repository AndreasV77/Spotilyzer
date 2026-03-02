"""
Theme-System (Buena Vista-inspiriert).

Neutrales Grau-Fundament + konfigurierbarer Accent-Color.
Dark und Light Mode, HSL-basiert.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ThemeMode(str, Enum):
    DARK = "dark"
    LIGHT = "light"


@dataclass
class ThemeColors:
    """Farb-Palette für ein Theme."""

    # Hintergrund-Stufen
    bg_primary: str = ""
    bg_alt: str = ""
    bg_card: str = ""
    bg_secondary: str = ""

    # Text
    text_normal: str = ""
    text_muted: str = ""

    # Accent (user-konfigurierbar)
    accent: str = ""
    accent_hover: str = ""

    # Feste Farben (mode-unabhängig)
    hit: str = "#22c55e"
    mid: str = "#eab308"
    flop: str = "#ef4444"

    # UI-Elemente
    border: str = ""
    scrollbar: str = ""
    scrollbar_hover: str = ""
    selection: str = ""


# Vordefinierte Paletten
DARK_COLORS = ThemeColors(
    bg_primary="#1a1a1a",
    bg_alt="#1d1d1d",
    bg_card="#232323",
    bg_secondary="#444444",
    text_normal="#ffffff",
    text_muted="#a5a5a5",
    accent="#89b4fa",
    accent_hover="#a6c8ff",
    border="#333333",
    scrollbar="#444444",
    scrollbar_hover="#555555",
    selection="#89b4fa33",
)

LIGHT_COLORS = ThemeColors(
    bg_primary="#ffffff",
    bg_alt="#fafafa",
    bg_card="#f4f4f4",
    bg_secondary="#cfcfcf",
    text_normal="#1a1a1a",
    text_muted="#6e6e6e",
    accent="#2563eb",
    accent_hover="#1d4ed8",
    border="#e0e0e0",
    scrollbar="#cccccc",
    scrollbar_hover="#bbbbbb",
    selection="#2563eb22",
)


class ThemeManager:
    """
    Verwaltet das aktuelle Theme und generiert QSS dynamisch.
    """

    def __init__(
        self,
        mode: ThemeMode = ThemeMode.DARK,
        accent_color: Optional[str] = None,
    ):
        self._mode = mode
        self._accent_override = accent_color
        self._colors = self._build_colors()

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @mode.setter
    def mode(self, value: ThemeMode | str) -> None:
        # QSettings / QComboBox können Strings statt Enums liefern
        if isinstance(value, str):
            try:
                value = ThemeMode(value)
            except (ValueError, KeyError):
                value = ThemeMode.DARK
        self._mode = value
        self._colors = self._build_colors()

    @property
    def accent_color(self) -> str:
        return self._accent_override or self._colors.accent

    @accent_color.setter
    def accent_color(self, value: str) -> None:
        self._accent_override = value
        self._colors = self._build_colors()

    @property
    def colors(self) -> ThemeColors:
        return self._colors

    def _build_colors(self) -> ThemeColors:
        """Erstellt die Farbpalette basierend auf Modus und Accent-Override."""
        if self._mode == ThemeMode.DARK:
            colors = ThemeColors(**vars(DARK_COLORS))
        else:
            colors = ThemeColors(**vars(LIGHT_COLORS))

        if self._accent_override:
            colors.accent = self._accent_override
            # Hover-Farbe: leicht heller/dunkler
            colors.accent_hover = self._accent_override

        return colors

    def generate_qss(self) -> str:
        """Generiert das komplette Qt-Stylesheet."""
        c = self._colors
        mode_label = self._mode.value if isinstance(self._mode, ThemeMode) else str(self._mode)
        is_dark = (self._mode == ThemeMode.DARK) if isinstance(self._mode, ThemeMode) else (str(self._mode) == "dark")
        return f"""
/* ═══════════════════════════════════════════════════════════════════ */
/*  Spotilyzer Theme — {mode_label.capitalize()} Mode          */
/* ═══════════════════════════════════════════════════════════════════ */

/* ── Basis ──────────────────────────────────────────────────────── */
QMainWindow {{
    background-color: {c.bg_primary};
}}

QWidget {{
    color: {c.text_normal};
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}}

/* ── Zentral-Widget ─────────────────────────────────────────────── */
#CentralWidget {{
    background-color: {c.bg_primary};
}}

/* ── Dock-Widgets ───────────────────────────────────────────────── */
QDockWidget {{
    color: {c.text_normal};
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}

QDockWidget::title {{
    background-color: {c.bg_alt};
    padding: 6px 10px;
    border-bottom: 1px solid {c.border};
    font-weight: bold;
    font-size: 12px;
}}

QDockWidget::close-button, QDockWidget::float-button {{
    border: none;
    background: transparent;
    padding: 2px;
}}

/* ── DropZone ───────────────────────────────────────────────────── */
#DropZone {{
    background-color: {c.bg_card};
    border: 2px dashed {c.border};
    border-radius: 12px;
}}

#DropZone[dragOver="true"] {{
    border-color: {c.accent};
    background-color: {c.selection};
}}

#DropZoneLabel {{
    color: {c.text_muted};
    font-size: 14px;
}}

/* ── Result Cards ───────────────────────────────────────────────── */
#ResultCard {{
    background-color: {c.bg_card};
    border: 1px solid {c.border};
    border-radius: 8px;
    padding: 10px;
}}

#ResultCard:hover {{
    border-color: {c.accent};
}}

/* ── Buttons ────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {c.bg_secondary};
    color: {c.text_normal};
    border: 1px solid {c.border};
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {c.scrollbar_hover};
    border-color: {c.accent};
}}

QPushButton:pressed {{
    background-color: {c.accent};
    color: {"#1a1a1a" if is_dark else "#ffffff"};
}}

QPushButton:disabled {{
    background-color: {c.bg_card};
    color: {c.text_muted};
    border-color: {c.bg_card};
}}

QPushButton#AccentButton {{
    background-color: {c.accent};
    color: {"#1a1a1a" if is_dark else "#ffffff"};
    border: none;
    font-weight: bold;
}}

QPushButton#AccentButton:hover {{
    background-color: {c.accent_hover};
}}

/* ── Sortier-Buttons (aktiv/inaktiv) ────────────────────────────── */
QPushButton#SortButtonActive {{
    background-color: {c.accent};
    color: {"#1a1a1a" if is_dark else "#ffffff"};
    border: none;
    font-weight: bold;
}}

QPushButton#SortButtonInactive {{
    background-color: {c.bg_secondary};
    color: {c.text_muted};
}}

/* ── Toolbar ────────────────────────────────────────────────────── */
QToolBar {{
    background-color: {c.bg_alt};
    border-bottom: 1px solid {c.border};
    padding: 4px;
    spacing: 6px;
}}

/* ── Tabs ────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {c.border};
    background-color: {c.bg_primary};
}}

QTabBar::tab {{
    background-color: {c.bg_alt};
    color: {c.text_muted};
    padding: 8px 16px;
    border: 1px solid {c.border};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {c.bg_primary};
    color: {c.text_normal};
    font-weight: bold;
    border-bottom: 2px solid {c.accent};
}}

QTabBar::tab:hover:!selected {{
    background-color: {c.bg_card};
    color: {c.text_normal};
}}

/* ── Tabellen ───────────────────────────────────────────────────── */
QTableView {{
    background-color: {c.bg_primary};
    alternate-background-color: {c.bg_alt};
    gridline-color: {c.border};
    selection-background-color: {c.selection};
    border: 1px solid {c.border};
}}

QTableView::item {{
    padding: 4px 8px;
}}

QHeaderView::section {{
    background-color: {c.bg_alt};
    color: {c.text_normal};
    padding: 6px 8px;
    border: none;
    border-bottom: 2px solid {c.border};
    font-weight: bold;
    font-size: 12px;
}}

/* ── Scrollbars ─────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background-color: transparent;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {c.scrollbar};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {c.scrollbar_hover};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 10px;
}}

QScrollBar::handle:horizontal {{
    background-color: {c.scrollbar};
    border-radius: 5px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {c.scrollbar_hover};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Input-Felder ───────────────────────────────────────────────── */
QLineEdit, QComboBox, QSpinBox {{
    background-color: {c.bg_card};
    color: {c.text_normal};
    border: 1px solid {c.border};
    border-radius: 6px;
    padding: 6px 10px;
}}

QLineEdit:focus, QComboBox:focus {{
    border-color: {c.accent};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {c.bg_card};
    color: {c.text_normal};
    border: 1px solid {c.border};
    selection-background-color: {c.accent};
}}

/* ── Labels ─────────────────────────────────────────────────────── */
QLabel {{
    color: {c.text_normal};
}}

QLabel#MutedLabel {{
    color: {c.text_muted};
    font-size: 11px;
}}

QLabel#TitleLabel {{
    font-size: 22px;
    font-weight: bold;
}}

QLabel#SubtitleLabel {{
    color: {c.accent};
    font-size: 12px;
}}

/* ── Stats-Leiste ───────────────────────────────────────────────── */
#StatsBar {{
    background-color: {c.bg_card};
    border-radius: 8px;
    padding: 8px 12px;
}}

/* ── Progress Bar ───────────────────────────────────────────────── */
QProgressBar {{
    background-color: {c.bg_card};
    border: 1px solid {c.border};
    border-radius: 4px;
    text-align: center;
    color: {c.text_normal};
    font-size: 11px;
    height: 18px;
}}

QProgressBar::chunk {{
    background-color: {c.accent};
    border-radius: 3px;
}}

/* ── Slider ─────────────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    background-color: {c.bg_secondary};
    height: 4px;
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background-color: {c.accent};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

QSlider::sub-page:horizontal {{
    background-color: {c.accent};
    border-radius: 2px;
}}

/* ── Splitter ───────────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {c.border};
}}

/* ── Tooltip ────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {c.bg_card};
    color: {c.text_normal};
    border: 1px solid {c.border};
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
}}

/* ── StatusBar ──────────────────────────────────────────────────── */
QStatusBar {{
    background-color: {c.bg_alt};
    color: {c.text_muted};
    border-top: 1px solid {c.border};
    font-size: 11px;
}}

/* ── Menu ───────────────────────────────────────────────────────── */
QMenuBar {{
    background-color: {c.bg_alt};
    color: {c.text_normal};
    border-bottom: 1px solid {c.border};
}}

QMenuBar::item:selected {{
    background-color: {c.accent};
}}

QMenu {{
    background-color: {c.bg_card};
    color: {c.text_normal};
    border: 1px solid {c.border};
}}

QMenu::item:selected {{
    background-color: {c.accent};
}}

/* ── Rating-spezifische Farben ──────────────────────────────────── */
.hit-color {{ color: {c.hit}; }}
.mid-color {{ color: {c.mid}; }}
.flop-color {{ color: {c.flop}; }}
"""
