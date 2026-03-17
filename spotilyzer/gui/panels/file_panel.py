"""
FilePanel — Datei-Browser als Dock-Widget.

QTreeView mit QFileSystemModel, gefiltert auf Audio-Dateien.
Ordner-Navigation mit Up/Home-Buttons und Pfadanzeige.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QDir, QModelIndex
from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeView,
    QFileSystemModel,
    QHeaderView,
    QLineEdit,
    QSizePolicy,
)

from spotilyzer import SUPPORTED_FORMATS


class FilePanel(QDockWidget):
    """
    Dock-Panel: Datei-Browser mit Ordner-Navigation.

    Zeigt Audio-Dateien im aktuellen Ordner als QTreeView.
    Doppelklick oder Auswahl startet die Analyse.

    Signals:
        files_selected(list[str]): Ausgewählte Dateipfade zur Analyse.
    """

    files_selected = Signal(list)
    folder_changed = Signal(Path)   # emitted on user-driven navigation

    def __init__(self, parent=None):
        super().__init__("Dateien", parent)
        self.setObjectName("FilePanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )

        # Aktueller Ordner
        self._current_path = Path.home()

        self._setup_ui()
        self._navigate_to(self._current_path)

    # ── UI-Aufbau ────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # ── Navigation: Up + Home + Pfadanzeige ──
        nav_bar = QHBoxLayout()
        nav_bar.setSpacing(4)

        self._btn_up = QPushButton("\u2b06")
        self._btn_up.setToolTip("Einen Ordner hoch")
        self._btn_up.setFixedSize(28, 28)
        self._btn_up.clicked.connect(self._on_navigate_up)
        nav_bar.addWidget(self._btn_up)

        self._btn_home = QPushButton("~")
        self._btn_home.setToolTip("Home-Verzeichnis")
        self._btn_home.setFixedSize(28, 28)
        self._btn_home.clicked.connect(self._on_navigate_home)
        nav_bar.addWidget(self._btn_home)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Ordnerpfad...")
        self._path_edit.returnPressed.connect(self._on_path_entered)
        nav_bar.addWidget(self._path_edit)

        layout.addLayout(nav_bar)

        # ── Analyse-Button ──
        self._btn_analyze = QPushButton("\u25b6  Auswahl analysieren")
        self._btn_analyze.setObjectName("AccentButton")
        self._btn_analyze.setEnabled(False)
        self._btn_analyze.clicked.connect(self._on_analyze_clicked)
        layout.addWidget(self._btn_analyze)

        # ── Datei-Baum ──
        self._model = QFileSystemModel()
        self._model.setReadOnly(True)

        # Filter: nur Audio-Formate + Ordner
        name_filters = [f"*{ext}" for ext in sorted(SUPPORTED_FORMATS)]
        self._model.setNameFilters(name_filters)
        self._model.setNameFilterDisables(False)  # Nicht-passende Dateien ausblenden

        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self._tree.setRootIsDecorated(False)
        self._tree.setSortingEnabled(True)
        self._tree.setAnimated(False)
        self._tree.setIndentation(16)
        self._tree.setAlternatingRowColors(True)

        # Spalten konfigurieren: Name, Size anzeigen; Type, Date ausblenden
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.setColumnWidth(1, 80)
        self._tree.setColumnHidden(2, True)  # Typ
        self._tree.setColumnHidden(3, True)  # Datum

        # Events
        self._tree.doubleClicked.connect(self._on_item_double_clicked)
        self._tree.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        ) if self._tree.selectionModel() else None

        layout.addWidget(self._tree)

        # ── Status-Zeile ──
        self._status_label = QLabel("Bereit")
        self._status_label.setObjectName("MutedLabel")
        layout.addWidget(self._status_label)

        self.setWidget(container)

    # ── Navigation ───────────────────────────────────────────────────

    def _navigate_to(self, path: Path, emit: bool = True) -> None:
        """Navigiert zum angegebenen Ordner."""
        if not path.is_dir():
            return

        self._current_path = path
        self._path_edit.setText(str(path))

        root_index = self._model.setRootPath(str(path))
        self._tree.setRootIndex(root_index)

        # Selection Model neu verbinden (wird bei setRootIndex neu erzeugt)
        sel_model = self._tree.selectionModel()
        if sel_model:
            sel_model.selectionChanged.connect(self._on_selection_changed)

        # Status aktualisieren
        self._update_status()
        if emit:
            self.folder_changed.emit(path)

    def _on_navigate_up(self) -> None:
        """Einen Ordner nach oben navigieren."""
        parent = self._current_path.parent
        if parent != self._current_path:
            self._navigate_to(parent)

    def _on_navigate_home(self) -> None:
        """Zum Home-Verzeichnis navigieren."""
        self._navigate_to(Path.home())

    def _on_path_entered(self) -> None:
        """Pfad aus dem Eingabefeld übernehmen."""
        text = self._path_edit.text().strip()
        if text:
            path = Path(text)
            if path.is_dir():
                self._navigate_to(path)
            else:
                self._path_edit.setText(str(self._current_path))

    # ── Datei-Auswahl ────────────────────────────────────────────────

    def _on_item_double_clicked(self, index: QModelIndex) -> None:
        """Doppelklick: Ordner öffnen oder Datei analysieren."""
        path = Path(self._model.filePath(index))

        if path.is_dir():
            self._navigate_to(path)
        elif path.suffix.lower() in SUPPORTED_FORMATS:
            self.files_selected.emit([str(path)])

    def _on_analyze_clicked(self) -> None:
        """Analyse-Button: Alle ausgewählten Dateien emittieren."""
        files = self._get_selected_files()
        if files:
            self.files_selected.emit(files)

    def _on_selection_changed(self) -> None:
        """Aktualisiert den Analyse-Button bei Auswahl-Änderung."""
        files = self._get_selected_files()
        count = len(files)
        self._btn_analyze.setEnabled(count > 0)
        if count > 0:
            self._btn_analyze.setText(
                f"\u25b6  {count} Datei{'en' if count != 1 else ''} analysieren"
            )
        else:
            self._btn_analyze.setText("\u25b6  Auswahl analysieren")

    def _get_selected_files(self) -> list[str]:
        """Gibt die ausgewählten Audio-Dateipfade zurück."""
        files: list[str] = []
        sel_model = self._tree.selectionModel()
        if not sel_model:
            return files

        for index in sel_model.selectedIndexes():
            if index.column() != 0:
                continue  # Nur Name-Spalte
            path = Path(self._model.filePath(index))
            if path.is_file() and path.suffix.lower() in SUPPORTED_FORMATS:
                files.append(str(path))
        return files

    def _update_status(self) -> None:
        """Aktualisiert die Status-Zeile mit Datei-Anzahl."""
        # Zähle Audio-Dateien im aktuellen Ordner
        count = 0
        for ext in SUPPORTED_FORMATS:
            count += len(list(self._current_path.glob(f"*{ext}")))
        self._status_label.setText(f"{count} Audio-Dateien in diesem Ordner")

    # ── Public API ───────────────────────────────────────────────────

    def set_folder(self, path) -> None:
        """Setzt den aktuellen Ordner programmatisch (kein folder_changed-Signal)."""
        p = Path(path) if not isinstance(path, Path) else path
        if p.is_dir():
            self._navigate_to(p, emit=False)
