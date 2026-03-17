"""
DropZone — Drag & Drop Zone für Audio-Dateien.
Qt-native Implementierung (kein tkinterdnd2).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from spotilyzer import SUPPORTED_FORMATS


class DropZone(QFrame):
    """
    Drag & Drop Zone für Audio-Dateien und Ordner.

    Signals:
        files_dropped(list[str]): Liste von Dateipfaden die gedroppt wurden.
    """

    files_dropped = Signal(list)
    browse_requested = Signal()   # Klick auf DropZone → Datei-Dialog

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel(
            "Audio-Dateien hierher ziehen\noder klicken zum Auswählen"
        )
        self._label.setObjectName("DropZoneLabel")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Mausereignisse an den Frame weiterleiten, nicht beim Label stoppen
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._label)

    def set_status(self, text: str) -> None:
        """Setzt den Label-Text."""
        self._label.setText(text)

    def set_loading(self, loading: bool) -> None:
        """Zeigt Lade-Status an."""
        if loading:
            self._label.setText("Modell wird geladen...")
            self.setEnabled(False)
        else:
            self._label.setText(
                "Audio-Dateien hierher ziehen\noder klicken zum Auswählen"
            )
            self.setEnabled(True)

    # ── Drag & Drop Events ──────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragOver", True)
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.setProperty("dragOver", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("dragOver", False)
        self.style().unpolish(self)
        self.style().polish(self)

        urls = event.mimeData().urls()
        audio_files = []

        for url in urls:
            path = Path(url.toLocalFile())

            if path.is_dir():
                # Ordner: rekursiv Audio-Dateien sammeln
                for ext in SUPPORTED_FORMATS:
                    audio_files.extend(
                        str(f) for f in path.rglob(f"*{ext}")
                    )
            elif path.suffix.lower() in SUPPORTED_FORMATS:
                audio_files.append(str(path))

        if audio_files:
            self.files_dropped.emit(audio_files)

    def mousePressEvent(self, event) -> None:
        """Klick emittiert browse_requested — Datei-Dialog wird im Parent geöffnet."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.browse_requested.emit()
        super().mousePressEvent(event)
