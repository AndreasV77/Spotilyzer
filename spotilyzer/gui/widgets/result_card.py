"""
ResultCard — Einzelnes Ergebnis-Widget für einen analysierten Track.

Kompaktes Layout:
  [Rang] [Dateiname]       [ConfidenceBar]  [Rating-Badge]
         [Audio-Info (optional, ab Ausgewogen)]
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout, QSizePolicy,
)

from spotilyzer.data.models import AnalysisResult, AppMode
from spotilyzer.gui.widgets.confidence_bar import ConfidenceBar


class ResultCard(QFrame):
    """
    Zeigt das Analyse-Ergebnis eines Tracks als kompakte Karte.

    Zeigt je nach AppMode unterschiedlich viele Details.
    Feste Höhe pro AppMode für Grid-Snap-Scrolling.
    """

    clicked = Signal(object)  # Emittiert AnalysisResult bei Klick

    RATING_COLORS = {"hit": "#22c55e", "mid": "#eab308", "flop": "#ef4444"}

    # Farbige Rang-Zahlen für Top 3 (kein Emoji — verhindert Segoe UI Emoji Hintergrundfarben)
    RANK_COLORS = {0: "#FFD700", 1: "#B8B8B8", 2: "#CD7F32"}  # Gold, Silber, Bronze

    # Feste Kartenhöhen pro Modus
    # SIMPLE:   margins(12) + header(~22) + spacing(4) + bar(20) = 58  → 68
    # BALANCED: + spacing(4) + audio_info(~16) = 78                    → 88
    # PRO:      + spacing(4) + CLAP-Zeile(~16) = 98                    → 104
    CARD_HEIGHTS = {
        AppMode.SIMPLE:   68,
        AppMode.BALANCED: 88,
        AppMode.PRO:      104,
    }

    # Kartenhöhe + Spacing ergibt die Rasterzeile
    CARD_SPACING = 4

    def __init__(
        self,
        result: AnalysisResult,
        rank: int = 0,
        app_mode: AppMode = AppMode.BALANCED,
        parent=None,
    ):
        super().__init__(parent)
        self.result = result
        self.rank = rank
        self.app_mode = app_mode

        self.setObjectName("ResultCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(self.CARD_HEIGHTS.get(app_mode, 88))
        self._setup_ui()

    @classmethod
    def row_height(cls, mode: AppMode) -> int:
        """Gesamthöhe einer Kartenzeile (Karte + Spacing)."""
        return cls.CARD_HEIGHTS.get(mode, 88) + cls.CARD_SPACING

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        if self.result.is_error:
            self._setup_error_ui(layout)
        else:
            self._setup_result_ui(layout)

    def _setup_error_ui(self, layout: QVBoxLayout):
        """Fehler-Karte."""
        label = QLabel(f"\u274c {self.result.file}")
        label.setObjectName("ErrorLabel")
        layout.addWidget(label)

        if self.result.error:
            err = QLabel(self.result.error)
            err.setObjectName("MutedLabel")
            err.setWordWrap(True)
            layout.addWidget(err)

    def _setup_result_ui(self, layout: QVBoxLayout):
        """Normale Ergebnis-Karte."""
        rating = self.result.rating
        color = self.RATING_COLORS.get(rating, "#a5a5a5")

        # ── Zeile 1: Rang + Dateiname + Rating-Badge ──
        header = QHBoxLayout()
        header.setSpacing(8)

        # Rang: Top-3 in Gold/Silber/Bronze, Rest gedimmt — kein Emoji
        rank_text = f"#{self.rank + 1}"
        rank_label = QLabel(rank_text)
        rank_label.setFixedWidth(34)
        rank_color = self.RANK_COLORS.get(self.rank)
        if rank_color:
            rank_label.setStyleSheet(
                f"color: {rank_color}; font-weight: bold; font-size: 13px;"
            )
            rank_label.setObjectName("MedalLabel")
        else:
            rank_label.setObjectName("RankLabel")
        header.addWidget(rank_label)

        # Dateiname
        display_name = self.result.file
        if len(display_name) > 70:
            display_name = display_name[:67] + "..."
        name_label = QLabel(display_name)
        name_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        name_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        name_label.setMinimumWidth(120)
        header.addWidget(name_label)

        header.addStretch()

        # Rating-Badge (farbig, kein Emoji)
        confidence = self.result.probabilities.get(rating, self.result.confidence)
        rating_label = QLabel(f" {rating.upper()} ({confidence:.0%}) ")
        rating_label.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 12px; "
            f"background-color: {color}18; border-radius: 4px; padding: 2px 6px;"
        )
        rating_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        header.addWidget(rating_label)

        layout.addLayout(header)

        # ── Zeile 2: Confidence-Bar (kompakt, gestapelt) ──
        self._confidence_bar = ConfidenceBar()
        self._confidence_bar.set_probabilities(self.result.probabilities)
        layout.addWidget(self._confidence_bar)

        # ── Zeile 3: Audio-Info (ab Ausgewogen) ──
        if self.app_mode != AppMode.SIMPLE and self.result.audio_info:
            self._add_audio_info(layout)

        # ── Zeile 4: CLAP Genre/Mood-Tags (ab Ausgewogen, wenn vorhanden) ──
        if self.app_mode != AppMode.SIMPLE and self.result.clap_result:
            self._add_clap_tags(layout)

    def _add_clap_tags(self, layout: QVBoxLayout):
        """Fügt CLAP Genre/Mood-Tags als kompakte Zeile hinzu."""
        clap = self.result.clap_result
        parts = []

        genre = clap.top_genre()
        mood = clap.top_mood()
        if genre:
            parts.append(f"Genre: {genre}")
        if mood:
            parts.append(mood)

        # Weitere Top-Tags (ohne genre/mood, max 3 zusätzlich)
        shown = {genre, mood} - {None}
        extras = [t for t in clap.top_tags if t not in shown][:3]
        if extras:
            parts.append("· " + " · ".join(extras))

        if not parts:
            return

        tags_label = QLabel("  ".join(parts))
        tags_label.setObjectName("MutedLabel")
        tags_label.setWordWrap(False)
        layout.addWidget(tags_label)

    def _add_audio_info(self, layout: QVBoxLayout):
        """Fügt technische Audio-Informationen als kompakte Zeile hinzu."""
        ai = self.result.audio_info
        if not ai:
            return

        info_parts = []

        # Ausgewogen: Duration, BPM, LUFS, Key, Format
        info_parts.append(ai.duration_formatted)

        if ai.bpm:
            info_parts.append(f"{ai.bpm:.0f} BPM")
        if ai.lufs is not None:
            info_parts.append(f"{ai.lufs:.1f} LUFS")
        if ai.key:
            info_parts.append(ai.key)
        info_parts.append(ai.format.upper())

        # Profi: Zusätzlich Sample-Rate, Bitrate, Channels, Dateigröße, Energy
        if self.app_mode == AppMode.PRO:
            info_parts.append(f"{ai.sample_rate} Hz")
            if ai.bitrate:
                info_parts.append(f"{ai.bitrate} kbps")
            info_parts.append(ai.channels_label)
            info_parts.append(ai.file_size_formatted)
            if ai.energy is not None:
                info_parts.append(f"E:{ai.energy:.2f}")

        info_text = " \u2502 ".join(info_parts)
        if len(info_text) > 130:
            info_text = info_text[:127] + "..."
        info_label = QLabel(info_text)
        info_label.setObjectName("MutedLabel")
        info_label.setWordWrap(False)
        layout.addWidget(info_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.result)
        super().mousePressEvent(event)
