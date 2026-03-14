"""
ConfidenceBar — Kompakter 3-Klassen Konfidenz-Balken (Hit/Mid/Flop).

Stacked-Bar: Alle drei Wahrscheinlichkeiten in einer horizontalen Zeile,
proportional nebeneinander, mit Prozent-Labels rechts.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QBrush, QFont, QPen
from PySide6.QtWidgets import QWidget, QSizePolicy


class ConfidenceBar(QWidget):
    """
    Kompakter gestapelter Balken: Hit | Mid | Flop nebeneinander,
    proportional zur Wahrscheinlichkeit. Rechts daneben die Labels.
    """

    COLORS = {
        "hit": QColor("#22c55e"),
        "mid": QColor("#eab308"),
        "flop": QColor("#ef4444"),
    }

    BAR_ORDER = ["hit", "mid", "flop"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._probabilities: dict[str, float] = {"hit": 0.0, "mid": 0.0, "flop": 0.0}

        self.setFixedHeight(26)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_probabilities(self, probabilities: dict) -> None:
        """Setzt die Wahrscheinlichkeiten und aktualisiert die Darstellung."""
        self._probabilities = {
            k: max(0.0, min(1.0, probabilities.get(k, 0.0)))
            for k in self.BAR_ORDER
        }
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        h = rect.height()
        radius = h / 2

        # Rechts Platz für Prozent-Labels lassen (3 Labels à ~48px)
        label_width = 145
        bar_width = max(0, rect.width() - label_width)

        # ── Hintergrund-Balken ──
        bg_rect = QRectF(0, 0, bar_width, h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#313244")))
        painter.drawRoundedRect(bg_rect, radius, radius)

        # ── Gestapelte Segmente ──
        total = sum(self._probabilities.values())
        if total > 0.01 and bar_width > 0:
            x = 0.0
            for key in self.BAR_ORDER:
                val = self._probabilities[key]
                if val < 0.005:
                    continue
                seg_w = (val / total) * bar_width
                # Mindestbreite für sichtbare Segmente
                seg_w = max(seg_w, 3.0) if val > 0.01 else seg_w

                seg_rect = QRectF(x, 0, seg_w, h)

                # Clipping: Rounded nur am Anfang/Ende
                painter.setBrush(QBrush(self.COLORS[key]))
                if x == 0 and x + seg_w >= bar_width - 1:
                    # Einziges Segment: beidseitig rund
                    painter.drawRoundedRect(seg_rect, radius, radius)
                elif x == 0:
                    # Erstes Segment: links rund
                    painter.drawRoundedRect(
                        QRectF(x, 0, seg_w + radius, h), radius, radius
                    )
                    painter.drawRect(QRectF(x + seg_w - 1, 0, radius + 1, h))
                elif x + seg_w >= bar_width - 1:
                    # Letztes Segment: rechts rund
                    painter.drawRoundedRect(
                        QRectF(x - radius, 0, seg_w + radius, h), radius, radius
                    )
                    painter.drawRect(QRectF(x - radius, 0, radius + 1, h))
                else:
                    # Mittleres Segment: eckig
                    painter.drawRect(seg_rect)

                x += seg_w

        # ── Prozent-Labels rechts ──
        label_x = bar_width + 8
        font = QFont("Segoe UI", 9)
        font.setBold(False)
        painter.setFont(font)

        for key in self.BAR_ORDER:
            val = self._probabilities[key]
            if val < 0.005:
                continue

            color = self.COLORS[key]
            text = f"{val:.0%}"

            painter.setPen(QPen(color))
            label_rect = QRectF(label_x, 0, 45, h)
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )
            label_x += 47

        painter.end()
