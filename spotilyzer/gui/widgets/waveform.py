"""
WaveformWidget — Audio-Wellenform-Visualisierung.

Custom QWidget mit paintEvent() für effizientes Rendering.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient
from PySide6.QtWidgets import QWidget, QSizePolicy


class WaveformWidget(QWidget):
    """
    Zeigt eine Audio-Waveform.

    Die Waveform-Daten sind ein 2D numpy Array [2, width]:
    - Row 0: Min-Werte pro Spalte
    - Row 1: Max-Werte pro Spalte

    Signals:
        position_clicked(float): Relative Position (0.0-1.0) bei Klick.
    """

    position_clicked = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._waveform_data: Optional[np.ndarray] = None
        self._playback_position: float = 0.0  # 0.0 - 1.0

        self._waveform_color = QColor("#22c55e")
        self._bg_color = QColor("#1a1a1a")
        self._position_color = QColor("#89b4fa")
        self._center_line_color = QColor("#333333")

        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_waveform(self, data: Optional[np.ndarray]) -> None:
        """Setzt die Waveform-Daten ([2, N] numpy Array)."""
        self._waveform_data = data
        self._playback_position = 0.0
        self.update()

    def set_playback_position(self, position: float) -> None:
        """Setzt die Playback-Position (0.0-1.0)."""
        self._playback_position = max(0.0, min(1.0, position))
        self.update()

    def clear(self) -> None:
        """Entfernt die Waveform."""
        self._waveform_data = None
        self._playback_position = 0.0
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        w, h = rect.width(), rect.height()

        # Hintergrund
        painter.fillRect(rect, self._bg_color)

        # Mittellinie
        painter.setPen(QPen(self._center_line_color, 1))
        center_y = h / 2
        painter.drawLine(0, int(center_y), w, int(center_y))

        if self._waveform_data is None or self._waveform_data.shape[1] == 0:
            # Platzhalter-Text
            painter.setPen(QPen(QColor("#555555")))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Keine Waveform")
            painter.end()
            return

        # Waveform zeichnen
        data = self._waveform_data
        n_points = data.shape[1]

        # Auf Widget-Breite skalieren
        x_scale = w / n_points if n_points > 0 else 1

        # Gradient für die Waveform
        gradient = QLinearGradient(0, 0, 0, h)
        gradient.setColorAt(0.0, self._waveform_color.lighter(130))
        gradient.setColorAt(0.5, self._waveform_color)
        gradient.setColorAt(1.0, self._waveform_color.lighter(130))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))

        # Zeichne Min/Max-Balken für jede Spalte
        for i in range(min(n_points, w)):
            idx = int(i / x_scale) if x_scale > 0 else i
            if idx >= n_points:
                idx = n_points - 1

            min_val = float(data[0, idx])
            max_val = float(data[1, idx])

            # Normalisieren auf Widget-Höhe
            y_min = center_y - max_val * center_y * 0.9
            y_max = center_y - min_val * center_y * 0.9

            bar_height = max(1, y_max - y_min)
            x = int(i * x_scale) if x_scale <= 1 else i

            painter.drawRect(x, int(y_min), max(1, int(x_scale)), int(bar_height))

        # Playback-Position (vertikale Linie)
        if self._playback_position > 0:
            pos_x = int(w * self._playback_position)
            painter.setPen(QPen(self._position_color, 2))
            painter.drawLine(pos_x, 0, pos_x, h)

        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._waveform_data is not None:
            rel_x = event.position().x() / self.width()
            self.position_clicked.emit(max(0.0, min(1.0, rel_x)))
        super().mousePressEvent(event)
