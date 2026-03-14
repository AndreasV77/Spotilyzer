"""
HistoryPanel — Chronologische Analyse-Übersicht als Dock-Widget.

QListWidget mit Timestamp + Dateiname + Rating.
Export-Buttons für alle 4 Formate (JSON, CSV, MD, TXT).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QMessageBox,
    QSizePolicy,
)

from spotilyzer.data.models import AnalysisResult
from spotilyzer.data.persistence import ResultExporter


class HistoryPanel(QDockWidget):
    """
    Dock-Panel: Chronologische Übersicht aller Analysen.

    Zeigt eine scrollbare Liste mit Timestamp, Dateiname und Rating.
    Export-Buttons für JSON, CSV, Markdown und Plain-Text.

    Signals:
        track_selected(AnalysisResult): Track wurde per Doppelklick ausgewählt.
    """

    track_selected = Signal(object)  # AnalysisResult

    # Rating-Farben für die Listen-Einträge
    RATING_COLORS = {
        "hit": QColor("#22c55e"),
        "mid": QColor("#eab308"),
        "flop": QColor("#ef4444"),
    }

    RATING_LABELS = {"hit": "HIT", "mid": "MID", "flop": "FLOP"}

    def __init__(self, parent=None):
        super().__init__("Verlauf", parent)
        self.setObjectName("HistoryPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )

        self._results: list[AnalysisResult] = []
        self._exporter = ResultExporter()
        self._setup_ui()

    # ── UI-Aufbau ────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # ── Header ──
        header = QHBoxLayout()

        title = QLabel("Verlauf")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(title)

        header.addStretch()

        self._count_label = QLabel("0 Einträge")
        self._count_label.setObjectName("MutedLabel")
        header.addWidget(self._count_label)

        layout.addLayout(header)

        # ── Listen-Widget ──
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list)

        # ── Export-Buttons ──
        export_label = QLabel("Exportieren:")
        export_label.setObjectName("MutedLabel")
        layout.addWidget(export_label)

        export_bar = QHBoxLayout()
        export_bar.setSpacing(4)

        self._btn_json = QPushButton("JSON")
        self._btn_json.setToolTip("Als JSON exportieren (re-importierbar)")
        self._btn_json.clicked.connect(lambda: self._export("json"))
        export_bar.addWidget(self._btn_json)

        self._btn_csv = QPushButton("CSV")
        self._btn_csv.setToolTip("Als CSV exportieren (Excel-kompatibel)")
        self._btn_csv.clicked.connect(lambda: self._export("csv"))
        export_bar.addWidget(self._btn_csv)

        self._btn_md = QPushButton("MD")
        self._btn_md.setToolTip("Als Markdown exportieren")
        self._btn_md.clicked.connect(lambda: self._export("md"))
        export_bar.addWidget(self._btn_md)

        self._btn_txt = QPushButton("TXT")
        self._btn_txt.setToolTip("Als Plain-Text exportieren")
        self._btn_txt.clicked.connect(lambda: self._export("txt"))
        export_bar.addWidget(self._btn_txt)

        layout.addLayout(export_bar)

        self.setWidget(container)

    # ── Public API ───────────────────────────────────────────────────

    def set_results(self, results: list[AnalysisResult]) -> None:
        """Setzt die Ergebnis-Liste und aktualisiert die Anzeige."""
        self._results = results
        self._rebuild_list()

    def set_exporter(self, exporter: ResultExporter) -> None:
        """Setzt den ResultExporter (für Device-Info im Export)."""
        self._exporter = exporter

    # ── Listen-Aufbau ────────────────────────────────────────────────

    def _rebuild_list(self) -> None:
        """Baut die Liste chronologisch sortiert neu auf (neueste zuerst)."""
        self._list.clear()

        # Chronologisch sortiert (neueste zuerst)
        sorted_results = sorted(
            self._results,
            key=lambda r: r.timestamp,
            reverse=True,
        )

        for result in sorted_results:
            self._add_item(result)

        # Status
        count = len(sorted_results)
        self._count_label.setText(
            f"{count} Eintrag{'e' if count != 1 else ''}"
        )

        # Export-Buttons aktivieren/deaktivieren
        has_results = count > 0
        self._btn_json.setEnabled(has_results)
        self._btn_csv.setEnabled(has_results)
        self._btn_md.setEnabled(has_results)
        self._btn_txt.setEnabled(has_results)

    def _add_item(self, result: AnalysisResult) -> None:
        """Fügt einen Eintrag zur Liste hinzu."""
        if result.is_error:
            text = f"\u274c  {result.timestamp[:16]}  {result.file}"
            item = QListWidgetItem(text)
            item.setForeground(QColor("#ef4444"))  # Flop-Rot: leserlich in dark + light
        else:
            rating_text = self.RATING_LABELS.get(result.rating, "?")
            hit_pct = result.probabilities.get("hit", 0.0)

            # Format: "Timestamp  RATING  Dateiname  (Hit%)"
            text = (
                f"{result.timestamp[:16]}  "
                f"{rating_text}  "
                f"{result.file}  "
                f"({hit_pct:.0%})"
            )
            item = QListWidgetItem(text)

            color = self.RATING_COLORS.get(result.rating, QColor("#888888"))
            item.setForeground(color)

        item.setToolTip(result.path)
        item.setData(Qt.ItemDataRole.UserRole, result)  # Referenz speichern
        self._list.addItem(item)

    # ── Events ───────────────────────────────────────────────────────

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Doppelklick: AnalysisResult aus dem Item extrahieren und emittieren."""
        result = item.data(Qt.ItemDataRole.UserRole)
        if result and isinstance(result, AnalysisResult):
            self.track_selected.emit(result)

    # ── Export ───────────────────────────────────────────────────────

    def _export(self, format_key: str) -> None:
        """Exportiert die Ergebnisse im gewählten Format."""
        if not self._results:
            return

        # Datei-Filter pro Format
        filters = {
            "json": ("JSON-Datei (*.json)", "json"),
            "csv": ("CSV-Datei (*.csv)", "csv"),
            "md": ("Markdown-Datei (*.md)", "md"),
            "txt": ("Text-Datei (*.txt)", "txt"),
        }

        filter_str, extension = filters[format_key]
        default_name = f"spotilyzer_export.{extension}"

        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Ergebnisse als {extension.upper()} exportieren",
            default_name,
            filter_str,
        )

        if not path:
            return  # Abgebrochen

        try:
            export_path = Path(path)

            if format_key == "json":
                self._exporter.to_json(self._results, export_path)
            elif format_key == "csv":
                self._exporter.to_csv(self._results, export_path)
            elif format_key == "md":
                self._exporter.to_markdown(self._results, export_path)
            elif format_key == "txt":
                self._exporter.to_text(self._results, export_path)

            QMessageBox.information(
                self,
                "Export erfolgreich",
                f"Ergebnisse wurden gespeichert:\n{export_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export-Fehler",
                f"Fehler beim Exportieren:\n{e}",
            )
