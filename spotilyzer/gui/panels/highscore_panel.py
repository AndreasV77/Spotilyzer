"""
HighscorePanel — Sortierbare Ranking-Tabelle als Dock-Widget.

QTableView mit QStandardItemModel, Spalten-Header-Klick zum Sortieren.
Doppelklick auf eine Zeile selektiert den Track.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor
from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QTableView,
    QHeaderView,
    QLabel,
    QAbstractItemView,
)

from spotilyzer.data.models import AnalysisResult, MEDALS


class HighscorePanel(QDockWidget):
    """
    Dock-Panel: Sortierbare Ranking-Tabelle aller Analyse-Ergebnisse.

    Spalten: Rank, File, Rating, Hit%, Mid%, Flop%, Confidence.
    Klick auf Header sortiert die Spalte.
    Doppelklick auf eine Zeile emittiert den Track.

    Signals:
        track_selected(AnalysisResult): Track wurde per Doppelklick ausgewählt.
    """

    track_selected = Signal(object)  # AnalysisResult

    # Spalten-Definition
    COLUMNS = ["#", "Datei", "Rating", "Hit%", "Mid%", "Flop%", "Konfidenz"]

    # Farben pro Rating
    RATING_COLORS = {
        "hit": QColor("#22c55e"),
        "mid": QColor("#eab308"),
        "flop": QColor("#ef4444"),
    }

    def __init__(self, parent=None):
        super().__init__("Highscore", parent)
        self.setObjectName("HighscorePanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )

        self._results: list[AnalysisResult] = []
        self._setup_ui()

    # ── UI-Aufbau ────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # ── Titel-Zeile ──
        header_layout = QVBoxLayout()
        self._title_label = QLabel("Ranking")
        self._title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(self._title_label)

        self._count_label = QLabel("Keine Ergebnisse")
        self._count_label.setObjectName("MutedLabel")
        header_layout.addWidget(self._count_label)

        layout.addLayout(header_layout)

        # ── Tabellen-Modell ──
        self._model = QStandardItemModel()
        self._model.setHorizontalHeaderLabels(self.COLUMNS)

        # Sortier-Proxy
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(Qt.ItemDataRole.UserRole)  # Numerische Sortierung

        # ── QTableView ──
        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)

        # Spaltenbreiten
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)      # Rang
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)    # Datei
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)      # Rating
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)      # Hit%
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)      # Mid%
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)      # Flop%
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)      # Konfidenz

        self._table.setColumnWidth(0, 40)
        self._table.setColumnWidth(2, 70)
        self._table.setColumnWidth(3, 65)
        self._table.setColumnWidth(4, 65)
        self._table.setColumnWidth(5, 65)
        self._table.setColumnWidth(6, 80)

        # Doppelklick-Event
        self._table.doubleClicked.connect(self._on_double_click)

        layout.addWidget(self._table)
        self.setWidget(container)

    # ── Public API ───────────────────────────────────────────────────

    def set_results(self, results: list[AnalysisResult]) -> None:
        """
        Setzt die Ergebnis-Liste und aktualisiert die Tabelle.

        Nur gültige Ergebnisse (ohne Fehler) werden angezeigt.
        Initial sortiert nach Hit-Wahrscheinlichkeit (absteigend).
        """
        self._results = results
        self._rebuild_table()

    # ── Tabellen-Aufbau ──────────────────────────────────────────────

    def _rebuild_table(self) -> None:
        """Baut die komplette Tabelle aus den aktuellen Ergebnissen neu auf."""
        self._model.removeRows(0, self._model.rowCount())

        valid = [r for r in self._results if not r.is_error]

        # Nach Hit-Score sortieren für initiale Rangvergabe
        ranked = sorted(
            valid,
            key=lambda r: r.probabilities.get("hit", 0.0),
            reverse=True,
        )

        for idx, result in enumerate(ranked):
            self._add_row(idx, result)

        # Status aktualisieren
        count = len(ranked)
        self._count_label.setText(
            f"{count} Track{'s' if count != 1 else ''}"
        )

        # Initial nach Hit% absteigend sortieren
        self._table.sortByColumn(3, Qt.SortOrder.DescendingOrder)

    def _add_row(self, rank: int, result: AnalysisResult) -> None:
        """Fügt eine Zeile zur Tabelle hinzu."""
        probs = result.probabilities
        hit_pct = probs.get("hit", 0.0)
        mid_pct = probs.get("mid", 0.0)
        flop_pct = probs.get("flop", 0.0)

        rating_color = self.RATING_COLORS.get(result.rating, QColor("#a5a5a5"))
        medal = MEDALS.get(rank, "")

        # Rang
        rank_item = QStandardItem(medal if medal else str(rank + 1))
        rank_item.setData(rank, Qt.ItemDataRole.UserRole)  # Numerisch sortierbar
        rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        # Dateiname
        file_item = QStandardItem(result.file)
        file_item.setData(result.file.lower(), Qt.ItemDataRole.UserRole)
        file_item.setToolTip(result.path)

        # Rating
        rating_text = result.rating.upper() if result.rating else "?"
        rating_item = QStandardItem(rating_text)
        rating_item.setData(
            {"hit": 3, "mid": 2, "flop": 1}.get(result.rating, 0),
            Qt.ItemDataRole.UserRole,
        )
        rating_item.setForeground(rating_color)
        rating_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        # Hit%
        hit_item = QStandardItem(f"{hit_pct:.1%}")
        hit_item.setData(hit_pct, Qt.ItemDataRole.UserRole)
        hit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Mid%
        mid_item = QStandardItem(f"{mid_pct:.1%}")
        mid_item.setData(mid_pct, Qt.ItemDataRole.UserRole)
        mid_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Flop%
        flop_item = QStandardItem(f"{flop_pct:.1%}")
        flop_item.setData(flop_pct, Qt.ItemDataRole.UserRole)
        flop_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Konfidenz
        conf_item = QStandardItem(f"{result.confidence:.1%}")
        conf_item.setData(result.confidence, Qt.ItemDataRole.UserRole)
        conf_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._model.appendRow([
            rank_item, file_item, rating_item,
            hit_item, mid_item, flop_item, conf_item,
        ])

    # ── Events ───────────────────────────────────────────────────────

    def _on_double_click(self, proxy_index) -> None:
        """Doppelklick auf eine Zeile: Track-Selection emittieren."""
        source_index = self._proxy.mapToSource(proxy_index)
        row = source_index.row()

        # AnalysisResult aus der Zeile rekonstruieren
        valid = [r for r in self._results if not r.is_error]
        ranked = sorted(
            valid,
            key=lambda r: r.probabilities.get("hit", 0.0),
            reverse=True,
        )

        if 0 <= row < len(ranked):
            self.track_selected.emit(ranked[row])
