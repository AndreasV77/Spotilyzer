"""
CentralWidget — Zentrales Widget der Hauptanwendung.

Enthält: DropZone + StatsBar + ResultList (scrollbar).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QFileDialog, QPushButton,
    QSizePolicy,
)

from spotilyzer import SUPPORTED_FORMATS
from spotilyzer.data.models import AnalysisResult, AppMode, SortMode, MEDALS
from spotilyzer.gui.widgets.dropzone import DropZone
from spotilyzer.gui.widgets.result_card import ResultCard


class CentralWidget(QWidget):
    """
    Zentrales Widget: DropZone oben, Stats in der Mitte, Ergebnisse unten.

    Signals:
        files_selected(list[str]): Dateien zum Analysieren ausgewählt.
        result_clicked(AnalysisResult): Ein Ergebnis wurde angeklickt.
    """

    files_selected = Signal(list)
    result_clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CentralWidget")
        self._results: list[AnalysisResult] = []
        self._sort_mode = SortMode.SCORE
        self._app_mode = AppMode.BALANCED
        self._open_dir: str = ""

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # ── Titel ──
        self._title_label = QLabel("\U0001f3b5 SPOTILYZER")
        self._title_label.setObjectName("TitleLabel")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_label)

        self._subtitle_label = QLabel("Hit/Mid/Flop Analyzer")
        self._subtitle_label.setObjectName("SubtitleLabel")
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._subtitle_label)

        # ── Status ──
        self._status_label = QLabel("\u2728 Initialisiere...")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        # ── DropZone ──
        self._dropzone = DropZone()
        self._dropzone.files_dropped.connect(self.files_selected.emit)
        self._dropzone.mousePressEvent = self._on_dropzone_click
        layout.addWidget(self._dropzone)

        # ── Toolbar: Sortierung + Buttons ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        sort_label = QLabel("Sortierung:")
        sort_label.setObjectName("MutedLabel")
        toolbar.addWidget(sort_label)

        self._sort_buttons = {}
        for mode, (text, icon) in [
            (SortMode.SCORE, ("Hit-Score", "\U0001f3c6")),
            (SortMode.TIME, ("Zuletzt", "\U0001f550")),
            (SortMode.NAME, ("Name", "\U0001f4dd")),
        ]:
            btn = QPushButton(f"{icon} {text}")
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, m=mode: self.set_sort_mode(m))
            toolbar.addWidget(btn)
            self._sort_buttons[mode] = btn

        toolbar.addStretch()

        self._clear_btn = QPushButton("\U0001f5d1\ufe0f Clear")
        self._clear_btn.setFixedHeight(28)
        self._clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(self._clear_btn)

        layout.addLayout(toolbar)
        self._update_sort_button_styles()

        # ── Stats-Leiste ──
        self._stats_bar = QLabel("Keine Ergebnisse")
        self._stats_bar.setObjectName("StatsBar")
        self._stats_bar.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._stats_bar)

        # ── Ergebnis-Bereich (scrollbar) ──
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._results_container = QWidget()
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(4)
        self._results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._scroll_area.setWidget(self._results_container)
        layout.addWidget(self._scroll_area, 1)  # stretch=1: nimmt verfügbaren Platz

    # ── Public API ──────────────────────────────────────────────────

    def set_open_dir(self, path: str) -> None:
        """Setzt das Standard-Verzeichnis für den Datei-Dialog."""
        self._open_dir = path

    def set_status(self, text: str) -> None:
        """Aktualisiert den Status-Text."""
        self._status_label.setText(text)

    def set_loading(self, loading: bool) -> None:
        """Setzt den Lade-Status der DropZone."""
        self._dropzone.set_loading(loading)

    def set_app_mode(self, mode: AppMode) -> None:
        """Setzt den App-Modus (beeinflusst Detail-Level der Karten)."""
        self._app_mode = mode
        self.refresh_display()

    def set_sort_mode(self, mode: SortMode) -> None:
        """Setzt den Sortier-Modus."""
        self._sort_mode = mode
        self._update_sort_button_styles()
        self.refresh_display()

    def set_results(self, results: list[AnalysisResult]) -> None:
        """Setzt die Ergebnis-Liste und aktualisiert die Anzeige."""
        self._results = results
        self.refresh_display()

    def add_result(self, result: AnalysisResult) -> None:
        """Fügt ein einzelnes Ergebnis hinzu."""
        self._results.append(result)
        self.refresh_display()

    def clear_results(self) -> None:
        """Löscht alle Ergebnisse."""
        self._results.clear()
        self.refresh_display()

    @property
    def results(self) -> list[AnalysisResult]:
        return self._results

    def refresh_display(self) -> None:
        """Aktualisiert die komplette Ergebnis-Anzeige."""
        # Alte Karten entfernen
        while self._results_layout.count() > 0:
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Sortiert einfügen
        sorted_results = self._get_sorted_results()
        for idx, result in enumerate(sorted_results):
            card = ResultCard(result, rank=idx, app_mode=self._app_mode)
            card.clicked.connect(self.result_clicked.emit)
            self._results_layout.insertWidget(idx, card)

        self._update_stats()

        # ── Layout-Anpassungen bei Ergebnissen ──
        has_results = len(sorted_results) > 0

        # Titel/Subtitle ausblenden wenn Ergebnisse vorhanden
        self._title_label.setVisible(not has_results)
        self._subtitle_label.setVisible(not has_results)

        # DropZone kollabieren wenn Ergebnisse vorhanden
        if has_results:
            self._dropzone.setMaximumHeight(50)
            self._dropzone.set_status(
                "\U0001f4c2 + Weitere Dateien ziehen oder klicken"
            )
        else:
            self._dropzone.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
            self._dropzone.set_status(
                "\U0001f4c2 Audio-Dateien hierher ziehen\noder klicken zum Auswählen"
            )

        # Scroll-Step auf Kartenhöhe setzen
        row_h = ResultCard.row_height(self._app_mode)
        self._scroll_area.verticalScrollBar().setSingleStep(row_h)

        # Viewport-Snap anwenden
        self._adjust_results_viewport()

    # ── Resize / Grid-Snap ─────────────────────────────────────────

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Passt den Ergebnis-Viewport an, damit nur vollständige Karten sichtbar sind."""
        super().resizeEvent(event)
        self._adjust_results_viewport()

    def _adjust_results_viewport(self) -> None:
        """Setzt Bottom-Margin des Results-Containers so, dass der Viewport
        ein exaktes Vielfaches der Kartenhöhe ist. Verhindert abgeschnittene Karten."""
        row_h = ResultCard.row_height(self._app_mode)
        if row_h <= 0:
            return

        viewport_h = self._scroll_area.viewport().height()
        if viewport_h <= 0:
            return

        remainder = viewport_h % row_h
        margins = self._results_layout.contentsMargins()
        self._results_layout.setContentsMargins(
            margins.left(), margins.top(), margins.right(), remainder
        )

    # ── Private ─────────────────────────────────────────────────────

    def _get_sorted_results(self) -> list[AnalysisResult]:
        """Gibt Ergebnisse sortiert zurück."""
        valid = [r for r in self._results if not r.is_error]

        if self._sort_mode == SortMode.SCORE:
            return sorted(valid, key=lambda r: r.hit_probability, reverse=True)
        elif self._sort_mode == SortMode.TIME:
            return sorted(valid, key=lambda r: r.timestamp, reverse=True)
        elif self._sort_mode == SortMode.NAME:
            return sorted(valid, key=lambda r: r.file.lower())
        return valid

    def _update_stats(self) -> None:
        """Aktualisiert die Stats-Leiste."""
        valid = [r for r in self._results if not r.is_error]
        if not valid:
            self._stats_bar.setText("Keine Ergebnisse")
            return

        hits = sum(1 for r in valid if r.rating == "hit")
        mids = sum(1 for r in valid if r.rating == "mid")
        flops = sum(1 for r in valid if r.rating == "flop")

        best = max(valid, key=lambda r: r.hit_probability)
        best_name = best.file[:25]
        best_score = best.hit_probability

        self._stats_bar.setText(
            f"\U0001f4ca {len(valid)} Tracks: {hits}\U0001f525 {mids}\u2796 {flops}\U0001f480  \u2502  "
            f"\U0001f3c6 Best: {best_name} ({best_score:.0%})"
        )

    def _update_sort_button_styles(self) -> None:
        """Markiert den aktiven Sortier-Button."""
        for mode, btn in self._sort_buttons.items():
            if mode == self._sort_mode:
                btn.setObjectName("SortButtonActive")
            else:
                btn.setObjectName("SortButtonInactive")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _on_dropzone_click(self, event) -> None:
        """Öffnet den Datei-Dialog bei Klick auf die DropZone."""
        if event.button() == Qt.MouseButton.LeftButton:
            extensions = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_FORMATS))
            files, _ = QFileDialog.getOpenFileNames(
                self,
                "Audio-Dateien auswählen",
                self._open_dir,
                f"Audio-Dateien ({extensions});;Alle Dateien (*.*)",
            )
            if files:
                self.files_selected.emit(files)

    def _on_clear(self) -> None:
        """Clear-Button Handler."""
        if self._results:
            self.clear_results()
            self.set_status("\U0001f5d1\ufe0f Ergebnisse gelöscht")
