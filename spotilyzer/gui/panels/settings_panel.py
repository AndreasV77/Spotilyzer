"""
SettingsPanel — Einstellungen als Dock-Widget.

View-Modus, Theme, Accent-Farbe, Device-Info, Export-Defaults,
Modell-Pfad. Persistiert über QSettings.
"""

from __future__ import annotations

import platform

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QCheckBox,
    QFrame,
    QColorDialog,
    QScrollArea,
    QSizePolicy,
    QGroupBox,
    QLineEdit,
    QFileDialog,
)
from PySide6.QtCore import QSettings

from spotilyzer.data.models import AppMode
from spotilyzer.gui.theme import ThemeMode


class SettingsPanel(QDockWidget):
    """
    Dock-Panel: Anwendungs-Einstellungen.

    Enthält View-Modus-Auswahl, Theme-Toggle, Accent-Farbwähler,
    Device-Info, Export-Defaults und Modell-Pfad.
    Einstellungen werden über QSettings persistiert.

    Signals:
        mode_changed(AppMode):   View-Modus wurde geändert.
        theme_changed(ThemeMode): Theme-Modus wurde geändert.
        accent_changed(str):      Accent-Farbe wurde geändert (Hex-String).
    """

    mode_changed = Signal(object)        # AppMode
    theme_changed = Signal(object)       # ThemeMode
    accent_changed = Signal(str)         # Hex-Farbcode
    home_dir_changed = Signal(str)       # Startordner (leer = deaktiviert)
    clap_enabled_changed = Signal(bool)  # CLAP ein/aus

    # QSettings Organisation
    _SETTINGS_ORG = "Spotilyzer"
    _SETTINGS_APP = "Spotilyzer"

    def __init__(self, parent=None):
        super().__init__("Einstellungen", parent)
        self.setObjectName("SettingsPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self._settings = QSettings(self._SETTINGS_ORG, self._SETTINGS_APP)
        self._setup_ui()
        self._load_settings()

    # ── UI-Aufbau ────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(8)

        # Scrollbar für kleine Panels
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(10)

        # ══════════════════════════════════════════════════════════════
        # Ansichts-Modus
        # ══════════════════════════════════════════════════════════════
        mode_group = QGroupBox("\U0001f4cb Ansicht")
        mode_layout = QFormLayout(mode_group)
        mode_layout.setSpacing(6)

        self._mode_combo = QComboBox()
        for app_mode in AppMode:
            self._mode_combo.addItem(app_mode.display_name, app_mode)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addRow("Modus:", self._mode_combo)

        mode_hint = QLabel(
            "Simpel = nur Rating | Ausgewogen = + Audio-Info | Profi = alles"
        )
        mode_hint.setObjectName("MutedLabel")
        mode_hint.setWordWrap(True)
        mode_layout.addRow(mode_hint)

        scroll_layout.addWidget(mode_group)

        # ══════════════════════════════════════════════════════════════
        # Theme
        # ══════════════════════════════════════════════════════════════
        theme_group = QGroupBox("\U0001f3a8 Theme")
        theme_layout = QFormLayout(theme_group)
        theme_layout.setSpacing(6)

        # Dark/Light Auswahl
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Dark", ThemeMode.DARK)
        self._theme_combo.addItem("Light", ThemeMode.LIGHT)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_layout.addRow("Modus:", self._theme_combo)

        # Accent-Farbe
        accent_row = QHBoxLayout()

        self._accent_btn = QPushButton()
        self._accent_btn.setFixedSize(32, 32)
        self._accent_btn.setToolTip("Accent-Farbe auswählen")
        self._accent_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._accent_btn.clicked.connect(self._on_accent_pick)
        accent_row.addWidget(self._accent_btn)

        self._accent_label = QLabel("#89b4fa")
        self._accent_label.setObjectName("MutedLabel")
        accent_row.addWidget(self._accent_label)

        accent_row.addStretch()

        self._accent_reset_btn = QPushButton("Reset")
        self._accent_reset_btn.setFixedWidth(50)
        self._accent_reset_btn.setToolTip("Accent-Farbe auf Standard zurücksetzen")
        self._accent_reset_btn.clicked.connect(self._on_accent_reset)
        accent_row.addWidget(self._accent_reset_btn)

        theme_layout.addRow("Accent:", accent_row)

        scroll_layout.addWidget(theme_group)

        # ══════════════════════════════════════════════════════════════
        # Gerät / System
        # ══════════════════════════════════════════════════════════════
        device_group = QGroupBox("\U0001f4bb System")
        device_layout = QFormLayout(device_group)
        device_layout.setSpacing(4)

        self._device_label = QLabel(self._detect_device_info())
        self._device_label.setWordWrap(True)
        self._device_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        device_layout.addRow("Device:", self._device_label)

        self._model_path_label = QLabel("spotilyzer_model.joblib")
        self._model_path_label.setWordWrap(True)
        self._model_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._model_path_label.setObjectName("MutedLabel")
        device_layout.addRow("Modell:", self._model_path_label)

        scroll_layout.addWidget(device_group)

        # ══════════════════════════════════════════════════════════════
        # Export-Defaults
        # ══════════════════════════════════════════════════════════════
        export_group = QGroupBox("\U0001f4be Export-Defaults")
        export_layout = QVBoxLayout(export_group)
        export_layout.setSpacing(4)

        self._chk_json = QCheckBox("JSON (strukturiert, re-importierbar)")
        self._chk_json.setChecked(True)
        self._chk_json.stateChanged.connect(self._save_settings)
        export_layout.addWidget(self._chk_json)

        self._chk_csv = QCheckBox("CSV (Excel/Sheets-kompatibel)")
        self._chk_csv.setChecked(False)
        self._chk_csv.stateChanged.connect(self._save_settings)
        export_layout.addWidget(self._chk_csv)

        self._chk_md = QCheckBox("Markdown (formatierter Report)")
        self._chk_md.setChecked(False)
        self._chk_md.stateChanged.connect(self._save_settings)
        export_layout.addWidget(self._chk_md)

        self._chk_txt = QCheckBox("TXT (Plain-Text)")
        self._chk_txt.setChecked(False)
        self._chk_txt.stateChanged.connect(self._save_settings)
        export_layout.addWidget(self._chk_txt)

        scroll_layout.addWidget(export_group)

        # ══════════════════════════════════════════════════════════════
        # Dateien
        # ══════════════════════════════════════════════════════════════
        files_group = QGroupBox("\U0001f4c1 Dateien")
        files_layout = QVBoxLayout(files_group)
        files_layout.setSpacing(6)

        home_dir_form = QFormLayout()
        home_dir_form.setSpacing(4)

        self._home_dir_edit = QLineEdit()
        self._home_dir_edit.setReadOnly(True)
        self._home_dir_edit.setPlaceholderText("Letzten Ordner verwenden...")
        home_dir_form.addRow("Startordner:", self._home_dir_edit)
        files_layout.addLayout(home_dir_form)

        home_dir_btn_row = QHBoxLayout()
        self._home_dir_browse_btn = QPushButton("Durchsuchen...")
        self._home_dir_browse_btn.clicked.connect(self._on_home_dir_browse)
        home_dir_btn_row.addWidget(self._home_dir_browse_btn)

        self._home_dir_reset_btn = QPushButton("Zurücksetzen")
        self._home_dir_reset_btn.clicked.connect(self._on_home_dir_reset)
        home_dir_btn_row.addWidget(self._home_dir_reset_btn)
        home_dir_btn_row.addStretch()
        files_layout.addLayout(home_dir_btn_row)

        home_dir_hint = QLabel("Leer = letzten verwendeten Ordner öffnen")
        home_dir_hint.setObjectName("MutedLabel")
        home_dir_hint.setWordWrap(True)
        files_layout.addWidget(home_dir_hint)

        scroll_layout.addWidget(files_group)

        # ══════════════════════════════════════════════════════════════
        # CLAP-Analyse
        # ══════════════════════════════════════════════════════════════
        clap_group = QGroupBox("🏷 CLAP Genre/Mood")
        clap_layout = QVBoxLayout(clap_group)
        clap_layout.setSpacing(6)

        self._chk_clap = QCheckBox("Genre- und Mood-Tags einbeziehen")
        self._chk_clap.setChecked(False)
        self._chk_clap.stateChanged.connect(self._on_clap_toggled)
        clap_layout.addWidget(self._chk_clap)

        clap_hint = QLabel(
            "Zero-Shot-Klassifikation via LAION CLAP.\n"
            "~776 MB Download beim ersten Start.\n"
            "Verlangsamt die Analyse um ~2–5 s/Track."
        )
        clap_hint.setObjectName("MutedLabel")
        clap_hint.setWordWrap(True)
        clap_layout.addWidget(clap_hint)

        # VRAM-Modus (relevant für GPUs ≤ 6 GB)
        vram_form = QFormLayout()
        vram_form.setSpacing(4)
        self._vram_combo = QComboBox()
        self._vram_combo.addItem("Sequenziell (≤ 6 GB VRAM)", "sequential")
        self._vram_combo.addItem("Gleichzeitig (> 6 GB VRAM)", "concurrent")
        self._vram_combo.currentIndexChanged.connect(self._save_settings)
        vram_form.addRow("VRAM-Modus:", self._vram_combo)
        clap_layout.addLayout(vram_form)

        scroll_layout.addWidget(clap_group)

        # ── Stretch am Ende ──
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        self.setWidget(container)

        # Initiale Accent-Farbe setzen
        self._update_accent_preview("#89b4fa")

    # ── Signale / Events ─────────────────────────────────────────────

    def _on_mode_changed(self, index: int) -> None:
        """View-Modus geändert."""
        mode = self._coerce_mode(self._mode_combo.currentData())
        if mode:
            self.mode_changed.emit(mode)
            self._save_settings()

    def _on_theme_changed(self, index: int) -> None:
        """Theme-Modus geändert."""
        theme = self._coerce_theme(self._theme_combo.currentData())
        if theme:
            self.theme_changed.emit(theme)
            self._save_settings()

    def _on_accent_pick(self) -> None:
        """Öffnet den Farbwähler-Dialog für die Accent-Farbe."""
        current = QColor(self._accent_label.text())
        color = QColorDialog.getColor(
            current, self, "Accent-Farbe wählen"
        )
        if color.isValid():
            hex_color = color.name()
            self._update_accent_preview(hex_color)
            self.accent_changed.emit(hex_color)
            self._save_settings()

    def _on_accent_reset(self) -> None:
        """Setzt die Accent-Farbe auf den Standard zurück."""
        # Standard-Farbe je nach Theme
        theme = self._coerce_theme(self._theme_combo.currentData())
        default_color = "#89b4fa" if theme == ThemeMode.DARK else "#2563eb"
        self._update_accent_preview(default_color)
        self.accent_changed.emit(default_color)
        self._save_settings()

    def _on_home_dir_browse(self) -> None:
        """Öffnet den Ordner-Auswahl-Dialog für den Startordner."""
        current = self._home_dir_edit.text()
        path = QFileDialog.getExistingDirectory(
            self, "Startordner auswählen", current or ""
        )
        if path:
            self._home_dir_edit.setText(path)
            self.home_dir_changed.emit(path)
            self._save_settings()

    def _on_home_dir_reset(self) -> None:
        """Löscht den konfigurierten Startordner."""
        self._home_dir_edit.clear()
        self.home_dir_changed.emit("")
        self._save_settings()

    def _on_clap_toggled(self, state: int) -> None:
        """CLAP-Checkbox geändert."""
        enabled = bool(state)
        self.clap_enabled_changed.emit(enabled)
        self._save_settings()

    def _update_accent_preview(self, hex_color: str) -> None:
        """Aktualisiert die Accent-Vorschau (Button-Hintergrund + Label)."""
        self._accent_btn.setStyleSheet(
            f"background-color: {hex_color}; "
            f"border: 2px solid {hex_color}; "
            f"border-radius: 4px;"
        )
        self._accent_label.setText(hex_color)

    # ── Public API ───────────────────────────────────────────────────

    def set_device_info(self, info: str) -> None:
        """Setzt die Device-Info-Anzeige (z.B. 'CUDA: NVIDIA RTX 4090')."""
        self._device_label.setText(info)

    def set_model_path(self, path: str) -> None:
        """Setzt die Modell-Pfad-Anzeige."""
        self._model_path_label.setText(path)

    def get_export_defaults(self) -> dict[str, bool]:
        """Gibt die aktuellen Export-Default-Einstellungen zurück."""
        return {
            "json": self._chk_json.isChecked(),
            "csv": self._chk_csv.isChecked(),
            "md": self._chk_md.isChecked(),
            "txt": self._chk_txt.isChecked(),
        }

    def get_current_mode(self) -> AppMode:
        """Gibt den aktuellen View-Modus zurück."""
        return self._coerce_mode(self._mode_combo.currentData()) or AppMode.BALANCED

    def get_current_theme(self) -> ThemeMode:
        """Gibt den aktuellen Theme-Modus zurück."""
        return self._coerce_theme(self._theme_combo.currentData()) or ThemeMode.DARK

    def get_accent_color(self) -> str:
        """Gibt die aktuelle Accent-Farbe als Hex-String zurück."""
        return self._accent_label.text()

    def get_clap_enabled(self) -> bool:
        """Gibt zurück ob CLAP-Analyse aktiviert ist."""
        return self._chk_clap.isChecked()

    def get_vram_mode(self) -> str:
        """Gibt den gewählten VRAM-Modus zurück ('sequential' oder 'concurrent')."""
        data = self._vram_combo.currentData()
        return str(data) if data else "sequential"

    # ── Persistenz (QSettings) ───────────────────────────────────────

    def _save_settings(self) -> None:
        """Speichert alle Einstellungen in QSettings."""
        mode = self._mode_combo.currentData()
        theme = self._theme_combo.currentData()

        if mode:
            # currentData() kann Enum oder String liefern (PySide6-Verhalten)
            mode_val = mode.value if hasattr(mode, "value") else str(mode)
            self._settings.setValue("view/mode", mode_val)
        if theme:
            theme_val = theme.value if hasattr(theme, "value") else str(theme)
            self._settings.setValue("theme/mode", theme_val)

        self._settings.setValue("theme/accent", self._accent_label.text())

        # Export-Defaults
        self._settings.setValue("export/json", self._chk_json.isChecked())
        self._settings.setValue("export/csv", self._chk_csv.isChecked())
        self._settings.setValue("export/md", self._chk_md.isChecked())
        self._settings.setValue("export/txt", self._chk_txt.isChecked())

        # Dateien
        self._settings.setValue("files/home_dir", self._home_dir_edit.text())

        # CLAP
        self._settings.setValue("analysis/clap_enabled", self._chk_clap.isChecked())
        vram_data = self._vram_combo.currentData()
        self._settings.setValue(
            "analysis/vram_mode",
            vram_data if vram_data else "sequential"
        )

        self._settings.sync()

    def _load_settings(self) -> None:
        """Lädt gespeicherte Einstellungen aus QSettings."""
        # View-Modus
        mode_val = self._settings.value("view/mode", AppMode.BALANCED.value)
        try:
            mode = AppMode(str(mode_val))
            # findData kann bei PySide6 fehlschlagen (str vs Enum),
            # daher über display_name suchen oder Index direkt setzen
            mode_list = list(AppMode)
            if mode in mode_list:
                self._mode_combo.setCurrentIndex(mode_list.index(mode))
        except (ValueError, KeyError):
            pass

        # Theme-Modus
        theme_val = self._settings.value("theme/mode", ThemeMode.DARK.value)
        try:
            theme = ThemeMode(str(theme_val))
            theme_list = list(ThemeMode)
            if theme in theme_list:
                self._theme_combo.setCurrentIndex(theme_list.index(theme))
        except (ValueError, KeyError):
            pass

        # Accent-Farbe
        accent = self._settings.value("theme/accent", "#89b4fa")
        if accent:
            self._update_accent_preview(accent)

        # Export-Defaults
        self._chk_json.setChecked(
            self._settings.value("export/json", True, type=bool)
        )
        self._chk_csv.setChecked(
            self._settings.value("export/csv", False, type=bool)
        )
        self._chk_md.setChecked(
            self._settings.value("export/md", False, type=bool)
        )
        self._chk_txt.setChecked(
            self._settings.value("export/txt", False, type=bool)
        )

        # Startordner
        home_dir = self._settings.value("files/home_dir", "")
        if home_dir:
            self._home_dir_edit.setText(home_dir)

        # CLAP
        clap_enabled = self._settings.value("analysis/clap_enabled", False, type=bool)
        self._chk_clap.setChecked(clap_enabled)
        vram_mode = self._settings.value("analysis/vram_mode", "sequential")
        vram_index = self._vram_combo.findData(str(vram_mode))
        if vram_index >= 0:
            self._vram_combo.setCurrentIndex(vram_index)

    # ── Hilfsfunktionen ──────────────────────────────────────────────

    @staticmethod
    def _coerce_mode(value) -> AppMode | None:
        """Stellt sicher, dass ein Wert von QComboBox als AppMode-Enum vorliegt.
        PySide6 kann Strings statt Enums aus currentData() liefern."""
        if value is None:
            return None
        if isinstance(value, AppMode):
            return value
        try:
            return AppMode(str(value))
        except (ValueError, KeyError):
            return None

    @staticmethod
    def _coerce_theme(value) -> ThemeMode | None:
        """Stellt sicher, dass ein Wert von QComboBox als ThemeMode-Enum vorliegt.
        PySide6 kann Strings statt Enums aus currentData() liefern."""
        if value is None:
            return None
        if isinstance(value, ThemeMode):
            return value
        try:
            return ThemeMode(str(value))
        except (ValueError, KeyError):
            return None

    @staticmethod
    def _detect_device_info() -> str:
        """Erkennt GPU/CPU-Information des Systems."""
        info_parts = [platform.processor() or platform.machine()]

        # Versuche torch-Device-Info (falls verfügbar)
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                info_parts = [f"CUDA: {gpu_name}"]
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                info_parts = ["MPS (Apple Silicon)"]
            else:
                info_parts.append("(CPU)")
        except ImportError:
            info_parts.append("(torch nicht verfügbar)")

        return " ".join(info_parts)
