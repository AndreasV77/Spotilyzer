"""
SpotilyzerApp — Hauptanwendung (QMainWindow).

Drei View-Modi: Simple / Tabbed / Full Dock.
Dock-Panels, Toolbar, Theme-Management, Pipeline-Integration.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QToolBar,
    QStatusBar,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QProgressBar,
    QMessageBox,
    QFileDialog,
    QLabel,
)

from spotilyzer import __version__, SUPPORTED_FORMATS
from spotilyzer.data.models import AnalysisResult, AppMode, SortMode
from spotilyzer.data.persistence import save_results, load_results, ResultExporter
from spotilyzer.gui.theme import ThemeManager, ThemeMode
from spotilyzer.gui.central import CentralWidget
from spotilyzer.gui.panels.file_panel import FilePanel
from spotilyzer.gui.panels.highscore_panel import HighscorePanel
from spotilyzer.gui.panels.history_panel import HistoryPanel
from spotilyzer.gui.panels.tech_panel import TechPanel
from spotilyzer.gui.panels.settings_panel import SettingsPanel
from spotilyzer.gui.worker import PipelineInitWorker, AnalysisWorker, WaveformWorker


# ══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════


class SpotilyzerApp(QMainWindow):
    """
    Hauptfenster der Spotilyzer-Anwendung.

    Features:
    - Drei View-Modi: Simple (nur DropZone+Ergebnisse), Tabbed (Tabs),
      Full (frei andockbare Panels).
    - Fünf Dock-Panels: Dateibrowser, Highscore, Verlauf, Technik, Einstellungen.
    - Theme-System (Dark/Light + konfigurierbarer Accent).
    - ML-Pipeline wird im Hintergrund initialisiert.
    - Auto-Save der Ergebnisse.
    """

    # QSettings Keys
    _SETTINGS_ORG = "Spotilyzer"
    _SETTINGS_APP = "Spotilyzer"

    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"Spotilyzer v{__version__}")
        self.setMinimumSize(1100, 720)
        self.resize(1600, 960)

        # State
        self._pipeline = None  # wird async geladen
        self._worker: Optional[AnalysisWorker] = None
        self._waveform_worker: Optional[WaveformWorker] = None
        self._app_mode = AppMode.BALANCED
        self._results: list[AnalysisResult] = []
        self._settings = QSettings(self._SETTINGS_ORG, self._SETTINGS_APP)

        # Dir-Persistenz
        self._last_open_dir: str = ""
        self._last_export_dir: str = ""
        self._home_dir: str = ""

        # Theme
        self._theme_manager = ThemeManager(ThemeMode.DARK)

        # UI aufbauen
        self._create_central_widget()
        self._create_dock_panels()
        self._create_toolbar()
        self._create_statusbar()
        self._create_menus()

        # Signale verbinden
        self._connect_signals()

        # Einstellungen laden
        self._load_app_settings()

        # Theme anwenden
        self._apply_theme()

        # Gespeicherte Ergebnisse laden
        self._load_saved_results()

        # Pipeline im Hintergrund initialisieren
        QTimer.singleShot(100, self._init_pipeline)

    # ── Dir-Persistenz ───────────────────────────────────────────────

    def _effective_open_dir(self) -> str:
        """Gibt das effektive Startverzeichnis zurück: home_dir > last_open_dir > ''."""
        return self._home_dir or self._last_open_dir or ""

    def set_home_dir(self, path: str) -> None:
        """Setzt den konfigurierten Startordner und aktualisiert alle Panels."""
        self._home_dir = path
        self._settings.setValue("files/home_dir", path)
        self._settings.sync()
        start = Path(path) if path else (
            Path(self._last_open_dir) if self._last_open_dir else Path.home()
        )
        self._file_panel.set_folder(start)
        self._central.set_open_dir(self._effective_open_dir())

    def _on_folder_changed(self, path: Path) -> None:
        """FilePanel: Benutzer hat zu einem Ordner navigiert — Pfad merken."""
        self._last_open_dir = str(path)
        self._settings.setValue("files/last_open_dir", self._last_open_dir)
        self._central.set_open_dir(self._effective_open_dir())

    # ── UI-Aufbau ────────────────────────────────────────────────────

    def _create_central_widget(self) -> None:
        """Erstellt das zentrale Widget (DropZone + Ergebnisse)."""
        self._central = CentralWidget()
        self.setCentralWidget(self._central)

    def _create_dock_panels(self) -> None:
        """Erstellt alle Dock-Panels."""
        # Dateibrowser (Links)
        self._file_panel = FilePanel(self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._file_panel)

        # Highscore (Unten)
        self._highscore_panel = HighscorePanel(self)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self._highscore_panel
        )

        # Verlauf (Unten, als Tab mit Highscore)
        self._history_panel = HistoryPanel(self)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self._history_panel
        )
        self.tabifyDockWidget(self._highscore_panel, self._history_panel)

        # Technik (Rechts)
        self._tech_panel = TechPanel(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._tech_panel)

        # Einstellungen (Rechts, als Tab mit Technik)
        self._settings_panel = SettingsPanel(self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._settings_panel
        )
        self.tabifyDockWidget(self._tech_panel, self._settings_panel)

        # Highscore als aktiven Tab setzen (unten)
        self._highscore_panel.raise_()
        # Technik als aktiven Tab setzen (rechts)
        self._tech_panel.raise_()

        # Initiale Dock-Größen (nur beim ersten Start, danach via QSettings)
        self.resizeDocks(
            [self._file_panel], [260], Qt.Orientation.Horizontal
        )
        self.resizeDocks(
            [self._tech_panel], [340], Qt.Orientation.Horizontal
        )
        self.resizeDocks(
            [self._highscore_panel], [280], Qt.Orientation.Vertical
        )

    def _create_toolbar(self) -> None:
        """Erstellt die Toolbar."""
        self._toolbar = QToolBar("Werkzeuge")
        self._toolbar.setObjectName("MainToolbar")
        self._toolbar.setMovable(False)
        self._toolbar.setFloatable(False)
        self.addToolBar(self._toolbar)

        # Ordner öffnen
        self._action_open = QAction("Öffnen", self)
        self._action_open.setShortcut(QKeySequence.StandardKey.Open)
        self._action_open.setToolTip("Audio-Dateien zum Analysieren auswählen")
        self._action_open.triggered.connect(self._on_open_files)
        self._toolbar.addAction(self._action_open)

        self._toolbar.addSeparator()

        # Export
        self._action_export = QAction("Export", self)
        self._action_export.setToolTip("Ergebnisse exportieren")
        self._action_export.triggered.connect(self._on_export)
        self._toolbar.addAction(self._action_export)

        # Clear
        self._action_clear = QAction("Clear", self)
        self._action_clear.setToolTip("Alle Ergebnisse löschen")
        self._action_clear.triggered.connect(self._on_clear)
        self._toolbar.addAction(self._action_clear)

        self._toolbar.addSeparator()

        # View-Modi
        self._action_simple = QAction("Simpel", self)
        self._action_simple.setToolTip("Einfache Ansicht — nur Rating + Ergebnisse")
        self._action_simple.triggered.connect(
            lambda: self._set_app_mode(AppMode.SIMPLE)
        )
        self._toolbar.addAction(self._action_simple)

        self._action_balanced = QAction("Ausgewogen", self)
        self._action_balanced.setToolTip(
            "Ausgewogene Ansicht — Rating + Audio-Info"
        )
        self._action_balanced.triggered.connect(
            lambda: self._set_app_mode(AppMode.BALANCED)
        )
        self._toolbar.addAction(self._action_balanced)

        self._action_pro = QAction("Profi", self)
        self._action_pro.setToolTip("Profi-Ansicht — alle Felder + Dock-Panels")
        self._action_pro.triggered.connect(
            lambda: self._set_app_mode(AppMode.PRO)
        )
        self._toolbar.addAction(self._action_pro)

        # Spacer
        spacer = QWidget()
        spacer.setFixedWidth(20)
        self._toolbar.addWidget(spacer)

        # Progress-Bar (in Toolbar)
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setFixedHeight(18)
        self._progress_bar.setVisible(False)
        self._toolbar.addWidget(self._progress_bar)

    def _create_statusbar(self) -> None:
        """Erstellt die Statusleiste."""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)

        self._status_device = QLabel("Device: ...")
        self._statusbar.addPermanentWidget(self._status_device)

    def _create_menus(self) -> None:
        """Erstellt die Menüleiste."""
        menubar = self.menuBar()

        # Datei-Menü
        file_menu = menubar.addMenu("&Datei")
        file_menu.addAction(self._action_open)
        file_menu.addAction(self._action_export)
        file_menu.addSeparator()

        action_quit = QAction("&Beenden", self)
        action_quit.setShortcut(QKeySequence.StandardKey.Quit)
        action_quit.triggered.connect(self.close)
        file_menu.addAction(action_quit)

        # Ansicht-Menü
        view_menu = menubar.addMenu("&Ansicht")
        view_menu.addAction(self._action_simple)
        view_menu.addAction(self._action_balanced)
        view_menu.addAction(self._action_pro)
        view_menu.addSeparator()

        # Panel-Toggle-Actions
        view_menu.addAction(self._file_panel.toggleViewAction())
        view_menu.addAction(self._highscore_panel.toggleViewAction())
        view_menu.addAction(self._history_panel.toggleViewAction())
        view_menu.addAction(self._tech_panel.toggleViewAction())
        view_menu.addAction(self._settings_panel.toggleViewAction())

        # Hilfe-Menü
        help_menu = menubar.addMenu("&Hilfe")
        action_about = QAction("Über Spotilyzer", self)
        action_about.triggered.connect(self._show_about)
        help_menu.addAction(action_about)

    # ── Signale verbinden ────────────────────────────────────────────

    def _connect_signals(self) -> None:
        """Verbindet alle Signale zwischen Widgets."""
        # Central Widget
        self._central.files_selected.connect(self._on_files_selected)
        self._central.result_clicked.connect(self._on_result_clicked)

        # File Panel
        self._file_panel.files_selected.connect(self._on_files_selected)
        self._file_panel.folder_changed.connect(self._on_folder_changed)

        # Highscore Panel
        self._highscore_panel.track_selected.connect(self._on_result_clicked)

        # History Panel
        self._history_panel.track_selected.connect(self._on_result_clicked)

        # Settings Panel
        self._settings_panel.mode_changed.connect(self._set_app_mode)
        self._settings_panel.theme_changed.connect(self._on_theme_changed)
        self._settings_panel.accent_changed.connect(self._on_accent_changed)
        self._settings_panel.home_dir_changed.connect(self.set_home_dir)
        self._settings_panel.device_changed.connect(self._on_device_changed)
        self._settings_panel.model_path_changed.connect(self._on_model_path_changed)

    # ── Pipeline-Initialisierung ─────────────────────────────────────

    def _init_pipeline(self) -> None:
        """Startet die Pipeline-Initialisierung im Hintergrund."""
        model_path = self._find_model_path()
        if not model_path:
            self._central.set_status(
                "\u274c Modell nicht gefunden! "
                "Bitte ein 'spotilyzer_model_*.joblib' in models/ bereitstellen "
                "oder unter Einstellungen > Modell einen Pfad angeben."
            )
            return

        self._central.set_status("Initialisiere ML-Pipeline...")
        self._settings_panel.set_model_path(str(model_path))

        device = self._settings_panel.get_device()
        self._init_worker = PipelineInitWorker(model_path, device=device, parent=self)
        self._init_worker.progress.connect(self._on_init_progress)
        self._init_worker.ready.connect(self._on_pipeline_ready)
        self._init_worker.error.connect(self._on_pipeline_error)
        self._init_worker.start()

    def _find_model_path(self) -> Optional[Path]:
        """Sucht das Modell — zuerst benutzerdefinierter Pfad, dann Auto-Erkennung."""
        # Benutzerdefinierter Pfad hat Vorrang
        custom = self._settings_panel.get_custom_model_path()
        if custom:
            p = Path(custom)
            if p.exists():
                return p

        # Verzeichnisse in Prioritätsreihenfolge
        models_dirs = [
            Path("models"),
            Path(__file__).parent.parent.parent / "models",
            Path.home() / ".spotilyzer" / "models",
        ]
        if getattr(sys, "frozen", False):
            models_dirs.insert(0, Path(sys._MEIPASS) / "models")

        for models_dir in models_dirs:
            # Neuestes spotilyzer_model_*.joblib bevorzugen
            found = sorted(
                models_dir.glob("spotilyzer_model_*.joblib"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if found:
                return found[0]
            # Fallback auf legacy-Dateiname
            legacy = models_dir / "spotilyzer_model.joblib"
            if legacy.exists():
                return legacy
        return None

    def _on_init_progress(self, message: str) -> None:
        """Pipeline-Initialisierung: Status-Update."""
        self._central.set_status(message)
        self._statusbar.showMessage(message, 5000)

    def _on_pipeline_ready(self, pipeline) -> None:
        """Pipeline erfolgreich initialisiert."""
        self._pipeline = pipeline

        device_display = pipeline.device_display
        self._central.set_status(
            f"\u2705 Bereit! Device: {device_display} | "
            f"Ziehe Audio-Dateien hierher oder klicke zum Auswählen"
        )
        self._status_device.setText(f"Device: {device_display}")
        self._settings_panel.set_device_info(device_display)

        # Exporter mit Pipeline-Infos konfigurieren
        self._exporter = ResultExporter(
            device_info=device_display,
            model_name=pipeline.predictor.model_name,
        )
        self._history_panel.set_exporter(self._exporter)

    def _on_pipeline_error(self, error_msg: str) -> None:
        """Pipeline-Initialisierung fehlgeschlagen."""
        self._central.set_status(f"\u274c Pipeline-Fehler: {error_msg}")
        QMessageBox.critical(
            self,
            "Pipeline-Fehler",
            f"Die ML-Pipeline konnte nicht initialisiert werden:\n\n{error_msg}",
        )

    def _on_device_changed(self, device: str) -> None:
        """Device-Auswahl geändert — Pipeline neu initialisieren."""
        from spotilyzer.core.embedder import MERTEmbedder
        MERTEmbedder.reset_instance()
        self._pipeline = None
        self._central.set_status(f"Device auf '{device}' geändert — lade Pipeline neu...")
        self._init_pipeline()

    def _on_model_path_changed(self, path: str) -> None:
        """Benutzerdefinierter Modell-Pfad geändert — Pipeline neu initialisieren."""
        from spotilyzer.core.embedder import MERTEmbedder
        MERTEmbedder.reset_instance()
        self._pipeline = None
        label = Path(path).name if path else "Auto-Erkennung"
        self._central.set_status(f"Modell geändert ({label}) — lade Pipeline neu...")
        self._init_pipeline()

    # ── Analyse ──────────────────────────────────────────────────────

    def _on_files_selected(self, files: list[str]) -> None:
        """Dateien zur Analyse ausgewählt (via Drop, Browse oder FilePanel)."""
        if not self._pipeline:
            QMessageBox.warning(
                self,
                "Nicht bereit",
                "Die ML-Pipeline wird noch initialisiert.\n"
                "Bitte warte einen Moment.",
            )
            return

        if self._worker and self._worker.isRunning():
            QMessageBox.information(
                self,
                "Analyse läuft",
                "Es läuft bereits eine Analyse.\n"
                "Bitte warte bis diese abgeschlossen ist.",
            )
            return

        # Worker starten
        self._central.set_loading(True)
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, len(files))
        self._progress_bar.setValue(0)

        include_waveform = self._app_mode in (AppMode.BALANCED, AppMode.PRO)
        include_clap = self._settings_panel.get_clap_enabled()
        vram_mode = self._settings_panel.get_vram_mode()

        self._worker = AnalysisWorker(
            pipeline=self._pipeline,
            files=files,
            include_audio_info=True,
            include_waveform=include_waveform,
            include_clap=include_clap,
            vram_mode=vram_mode,
            parent=self,
        )
        self._worker.progress.connect(self._on_analysis_progress)
        self._worker.result_ready.connect(self._on_result_ready)
        self._worker.batch_progress.connect(self._on_batch_progress)
        self._worker.finished_all.connect(self._on_analysis_finished)
        self._worker.error.connect(self._on_analysis_error)
        self._worker.start()

    def _on_analysis_progress(self, message: str) -> None:
        """Analyse: Status-Update."""
        self._central.set_status(message)
        self._statusbar.showMessage(message, 3000)

    def _on_result_ready(self, result: AnalysisResult) -> None:
        """Einzelnes Analyse-Ergebnis bereit."""
        self._results.append(result)
        self._central.add_result(result)

        # Panels aktualisieren
        self._highscore_panel.set_results(self._results)
        self._history_panel.set_results(self._results)

        # Waveform nachladen falls nicht enthalten
        if result._waveform is None and not result.is_error:
            self._start_waveform_load(result)

    def _on_batch_progress(self, current: int, total: int) -> None:
        """Batch-Fortschritt aktualisieren."""
        self._progress_bar.setValue(current)

    def _on_analysis_finished(self) -> None:
        """Alle Analysen abgeschlossen."""
        count = len(self._results)
        self._central.set_loading(False)
        self._progress_bar.setVisible(False)

        # Status
        valid = [r for r in self._results if not r.is_error]
        hits = sum(1 for r in valid if r.rating == "hit")
        self._central.set_status(
            f"\u2705 {count} Tracks analysiert | "
            f"{hits} Hits gefunden"
        )

        # Auto-Save
        self._auto_save()

    def _on_analysis_error(self, error_msg: str) -> None:
        """Analyse-Fehler für einzelnen Track."""
        self._statusbar.showMessage(f"Fehler: {error_msg}", 5000)

    # ── Waveform-Loading ─────────────────────────────────────────────

    def _start_waveform_load(self, result: AnalysisResult) -> None:
        """Startet das Waveform-Loading im Hintergrund."""
        worker = WaveformWorker(result.path, parent=self)
        worker.ready.connect(self._on_waveform_ready)
        worker.start()
        # Referenz halten damit der Worker nicht GC'd wird
        if not hasattr(self, "_waveform_workers"):
            self._waveform_workers: list[WaveformWorker] = []
        self._waveform_workers.append(worker)

    def _on_waveform_ready(self, filepath: str, waveform_data) -> None:
        """Waveform-Daten sind bereit."""
        # Ergebnis finden und Waveform zuweisen
        for result in self._results:
            if result.path == filepath:
                result._waveform = waveform_data
                # Falls dieser Track gerade im TechPanel angezeigt wird, updaten
                if (
                    self._tech_panel._current_result
                    and self._tech_panel._current_result.path == filepath
                ):
                    self._tech_panel._waveform.set_waveform(waveform_data)
                break

    # ── Result-Auswahl ───────────────────────────────────────────────

    def _on_result_clicked(self, result: AnalysisResult) -> None:
        """Ein Ergebnis wurde angeklickt — Details im TechPanel anzeigen."""
        self._tech_panel.set_result(result)
        self._tech_panel.show()
        self._tech_panel.raise_()

        # Waveform nachladen falls nicht enthalten (z. B. nach JSON-Import)
        if result._waveform is None and not result.is_error:
            self._start_waveform_load(result)

    # ── View-Modi ────────────────────────────────────────────────────

    def _set_app_mode(self, mode: AppMode) -> None:
        """Setzt den View-Modus und passt die Sichtbarkeit der Panels an."""
        # PySide6 QComboBox/Signal kann Strings statt Enums liefern
        if not isinstance(mode, AppMode):
            try:
                mode = AppMode(str(mode))
            except (ValueError, KeyError):
                mode = AppMode.BALANCED
        self._app_mode = mode
        self._central.set_app_mode(mode)

        if mode == AppMode.SIMPLE:
            # Alle Panels ausblenden
            self._file_panel.hide()
            self._highscore_panel.hide()
            self._history_panel.hide()
            self._tech_panel.hide()
            self._settings_panel.hide()

        elif mode == AppMode.BALANCED:
            # Wichtige Panels zeigen
            self._file_panel.hide()
            self._highscore_panel.show()
            self._history_panel.show()
            self._tech_panel.show()
            self._settings_panel.hide()

        elif mode == AppMode.PRO:
            # Alle Panels zeigen
            self._file_panel.show()
            self._highscore_panel.show()
            self._history_panel.show()
            self._tech_panel.show()
            self._settings_panel.show()

        self._update_mode_actions()
        self._save_app_settings()

    def _update_mode_actions(self) -> None:
        """Aktualisiert die visuellen Markierungen der Mode-Buttons."""
        modes = {
            AppMode.SIMPLE: self._action_simple,
            AppMode.BALANCED: self._action_balanced,
            AppMode.PRO: self._action_pro,
        }
        for m, action in modes.items():
            action.setChecked(m == self._app_mode)

    # ── Theme ────────────────────────────────────────────────────────

    def _on_theme_changed(self, theme_mode) -> None:
        """Theme-Modus wurde geändert."""
        # ThemeManager.mode setter handles string coercion
        self._theme_manager.mode = theme_mode
        self._apply_theme()

    def _on_accent_changed(self, hex_color: str) -> None:
        """Accent-Farbe wurde geändert."""
        self._theme_manager.accent_color = hex_color
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Wendet das aktuelle Theme als QSS + QPalette an.

        QPalette dient als Fallback für Widgets die kein Custom-QSS
        vollständig respektieren (z.B. tabifizierte Dock-TabBars).
        """
        c = self._theme_manager.colors
        app = QApplication.instance()

        # QSS — primäre Styling-Quelle
        app.setStyleSheet(self._theme_manager.generate_qss())

        # QPalette — Fallback für platform-native Bereiche
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window,          QColor(c.bg_primary))
        palette.setColor(QPalette.ColorRole.WindowText,      QColor(c.text_normal))
        palette.setColor(QPalette.ColorRole.Base,            QColor(c.bg_card))
        palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(c.bg_alt))
        palette.setColor(QPalette.ColorRole.Text,            QColor(c.text_normal))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(c.text_muted))
        palette.setColor(QPalette.ColorRole.Button,          QColor(c.bg_secondary))
        palette.setColor(QPalette.ColorRole.ButtonText,      QColor(c.text_normal))
        palette.setColor(QPalette.ColorRole.Highlight,       QColor(c.accent))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor(c.bg_card))
        palette.setColor(QPalette.ColorRole.ToolTipText,     QColor(c.text_normal))
        palette.setColor(QPalette.ColorRole.Link,            QColor(c.accent))
        palette.setColor(QPalette.ColorRole.Mid,             QColor(c.bg_secondary))
        palette.setColor(QPalette.ColorRole.Dark,            QColor(c.border))
        app.setPalette(palette)

    # ── Datei-Aktionen ───────────────────────────────────────────────

    def _on_open_files(self) -> None:
        """Öffnet den Datei-Dialog."""
        extensions = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_FORMATS))
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Audio-Dateien auswählen",
            self._effective_open_dir(),
            f"Audio-Dateien ({extensions});;Alle Dateien (*.*)",
        )
        if files:
            self._last_open_dir = str(Path(files[0]).parent)
            self._settings.setValue("files/last_open_dir", self._last_open_dir)
            self._central.set_open_dir(self._effective_open_dir())
            self._on_files_selected(files)

    def _on_export(self) -> None:
        """Exportiert Ergebnisse."""
        if not self._results:
            QMessageBox.information(
                self, "Kein Export", "Keine Ergebnisse zum Exportieren."
            )
            return

        if not hasattr(self, "_exporter"):
            self._exporter = ResultExporter()

        # Export-Defaults aus Settings
        defaults = self._settings_panel.get_export_defaults()

        # Export-Dialog
        default_name = (
            str(Path(self._last_export_dir) / "spotilyzer_export")
            if self._last_export_dir
            else "spotilyzer_export"
        )
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Ergebnisse exportieren",
            default_name,
            "JSON (*.json);;CSV (*.csv);;Markdown (*.md);;Text (*.txt)",
        )
        if not path:
            return

        export_path = Path(path)
        try:
            if selected_filter.startswith("JSON") or export_path.suffix == ".json":
                self._exporter.to_json(self._results, export_path)
            elif selected_filter.startswith("CSV") or export_path.suffix == ".csv":
                self._exporter.to_csv(self._results, export_path)
            elif (
                selected_filter.startswith("Markdown") or export_path.suffix == ".md"
            ):
                self._exporter.to_markdown(self._results, export_path)
            elif selected_filter.startswith("Text") or export_path.suffix == ".txt":
                self._exporter.to_text(self._results, export_path)
            else:
                # Default: JSON
                if not export_path.suffix:
                    export_path = export_path.with_suffix(".json")
                self._exporter.to_json(self._results, export_path)

            self._last_export_dir = str(export_path.parent)
            self._settings.setValue("files/last_export_dir", self._last_export_dir)
            self._statusbar.showMessage(
                f"\u2705 Export gespeichert: {export_path}", 5000
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Export-Fehler", f"Fehler beim Exportieren:\n{e}"
            )

    def _on_clear(self) -> None:
        """Löscht alle Ergebnisse."""
        if not self._results:
            return

        reply = QMessageBox.question(
            self,
            "Ergebnisse löschen?",
            f"{len(self._results)} Ergebnisse werden gelöscht.\nFortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._results.clear()
        self._central.clear_results()
        self._highscore_panel.set_results([])
        self._history_panel.set_results([])
        self._tech_panel.clear()
        self._central.set_status("Ergebnisse gelöscht")

    # ── Persistenz ───────────────────────────────────────────────────

    def _auto_save(self) -> None:
        """Speichert Ergebnisse automatisch."""
        try:
            save_results(self._results)
        except Exception:
            pass  # Silent fail für Auto-Save

    def _load_saved_results(self) -> None:
        """Lädt gespeicherte Ergebnisse beim Start."""
        results = load_results()
        if results:
            self._results = results
            self._central.set_results(results)
            self._highscore_panel.set_results(results)
            self._history_panel.set_results(results)

    # ── Settings-Persistenz ──────────────────────────────────────────

    def _save_app_settings(self) -> None:
        """Speichert App-spezifische Einstellungen."""
        mode_val = self._app_mode.value if isinstance(self._app_mode, AppMode) else str(self._app_mode)
        self._settings.setValue("app/mode", mode_val)
        self._settings.setValue("window/state", self.saveState())
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.sync()

    def _load_app_settings(self) -> None:
        """Lädt gespeicherte App-Einstellungen."""
        # App-Modus
        mode_val = self._settings.value("app/mode", AppMode.BALANCED.value)
        try:
            self._app_mode = AppMode(mode_val)
        except (ValueError, KeyError):
            self._app_mode = AppMode.BALANCED

        # Theme aus Settings-Panel übernehmen
        theme_mode = self._settings_panel.get_current_theme()
        self._theme_manager.mode = theme_mode

        accent = self._settings_panel.get_accent_color()
        if accent and accent != "#89b4fa":
            self._theme_manager.accent_color = accent

        # View-Modus anwenden
        self._set_app_mode(self._app_mode)

        # Window-State wiederherstellen
        geometry = self._settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)

        state = self._settings.value("window/state")
        if state:
            self.restoreState(state)

        # Dir-Persistenz laden
        self._last_open_dir = self._settings.value("files/last_open_dir", "")
        self._last_export_dir = self._settings.value("files/last_export_dir", "")
        self._home_dir = self._settings.value("files/home_dir", "")

        # Panels mit gespeichertem Startordner initialisieren
        start_dir = self._home_dir or self._last_open_dir
        if start_dir:
            self._file_panel.set_folder(Path(start_dir))
        self._central.set_open_dir(self._effective_open_dir())

    # ── Window-Events ────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Speichert State beim Schließen."""
        # Laufende Worker stoppen
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)

        # State speichern
        self._save_app_settings()
        self._auto_save()

        event.accept()

    # ── Hilfe ────────────────────────────────────────────────────────

    def _show_about(self) -> None:
        """Zeigt den Über-Dialog."""
        device = "..."
        if self._pipeline:
            device = self._pipeline.device_display

        model_info = ""
        if self._pipeline and self._pipeline.model_info:
            mi = self._pipeline.model_info
            model_info = f"\nModell: {mi.model_name}"
            if mi.training_date:
                model_info += f"\nTrainiert: {mi.training_date}"
            if mi.dataset_info:
                model_info += f"\nDatensatz: {mi.dataset_info}"

        QMessageBox.about(
            self,
            "Über Spotilyzer",
            f"Spotilyzer v{__version__}\n\n"
            f"Hit/Mid/Flop Analyzer\n"
            f"Bewertet die Mainstream-Kompatibilität von Audio-Tracks.\n\n"
            f"ML-Pipeline: MERT-v1-95M + XGBoost\n"
            f"Device: {device}"
            f"{model_info}\n\n"
            f"GUI: PySide6 (Qt 6)\n"
            f"Theme: Buena Vista-inspiriert",
        )


# ══════════════════════════════════════════════════════════════════════════════
# APPLICATION RUNNER
# ══════════════════════════════════════════════════════════════════════════════


def run_app() -> int:
    """Startet die Spotilyzer-Anwendung."""
    app = QApplication.instance() or QApplication(sys.argv)
    # Fusion-Style: Qt-eigene Implementierung, ignoriert platform-native Overrides
    # und respektiert Custom-QSS vollständig (kein Windows-Theme-Bleed).
    app.setStyle("Fusion")
    app.setApplicationName("Spotilyzer")
    app.setOrganizationName("Spotilyzer")
    app.setApplicationVersion(__version__)

    # Icon setzen (falls vorhanden)
    icon_path = Path(__file__).parent.parent.parent / "resources" / "spotilyzer.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = SpotilyzerApp()
    window.show()

    return app.exec()
