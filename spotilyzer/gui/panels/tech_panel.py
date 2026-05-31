"""
TechPanel — Technische Detail-Ansicht als Dock-Widget.

Zeigt alle AudioInfo-Felder in einem QFormLayout.
Enthält WaveformWidget und Audio-Player (QMediaPlayer).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Slot
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QPushButton,
    QSlider,
    QFrame,
    QScrollArea,
    QSizePolicy,
)

from spotilyzer.data.models import AnalysisResult, AudioInfo
from spotilyzer.gui.widgets.waveform import WaveformWidget


class TechPanel(QDockWidget):
    """
    Dock-Panel: Technische Daten und Audio-Player.

    Zeigt alle AudioInfo-Felder, eingebettete Waveform-Visualisierung
    und einen Audio-Player mit Play/Stop, Seek-Slider und Zeitanzeige.
    """

    def __init__(self, parent=None):
        super().__init__("Technik", parent)
        self.setObjectName("TechPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )

        self._current_result: AnalysisResult | None = None
        self._is_seeking = False  # Verhindert Slider-Feedback-Loop

        self._setup_ui()
        self._setup_player()

    # ── UI-Aufbau ────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # ── Track-Titel ──
        self._track_label = QLabel("Kein Track ausgewählt")
        self._track_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._track_label.setWordWrap(True)
        main_layout.addWidget(self._track_label)

        self._rating_label = QLabel("")
        self._rating_label.setObjectName("MutedLabel")
        main_layout.addWidget(self._rating_label)

        # ── Scrollbarer Bereich für Metadaten ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_content.setObjectName("TechScrollContent")
        scroll_content.setAutoFillBackground(False)
        scroll_content.setStyleSheet("#TechScrollContent { background-color: transparent; }")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(8)

        # ── Audio-Info Formular ──
        self._form = QFormLayout()
        self._form.setSpacing(4)
        self._form.setContentsMargins(0, 0, 0, 0)
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Felder vorbereiten (Label -> QLabel-Widget)
        self._info_fields: dict[str, QLabel] = {}
        field_defs = [
            ("Dauer", "duration"),
            ("Format", "format"),
            ("Sample-Rate", "sample_rate"),
            ("Channels", "channels"),
            ("Bitrate", "bitrate"),
            ("Dateigröße", "file_size"),
            ("BPM", "bpm"),
            ("LUFS", "lufs"),
            ("Tonart", "key"),
            ("Centroid", "spectral_centroid"),
            ("Flatness", "spectral_flatness"),
            ("Onset-Rate", "onset_rate"),
        ]

        for display_name, field_key in field_defs:
            value_label = QLabel("\u2014")
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self._info_fields[field_key] = value_label
            self._form.addRow(f"{display_name}:", value_label)

        scroll_layout.addLayout(self._form)

        # ── Trennlinie ──
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        scroll_layout.addWidget(separator)

        # ── Waveform ──
        waveform_title = QLabel("Waveform")
        waveform_title.setStyleSheet("font-weight: bold; font-size: 12px;")
        scroll_layout.addWidget(waveform_title)

        self._waveform = WaveformWidget()
        self._waveform.setMinimumHeight(80)
        self._waveform.position_clicked.connect(self._on_waveform_clicked)
        scroll_layout.addWidget(self._waveform)

        # ── Ähnliche Tracks ──
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        scroll_layout.addWidget(sep2)

        similar_title = QLabel("Klingt ähnlich wie")
        similar_title.setStyleSheet("font-weight: bold; font-size: 12px;")
        scroll_layout.addWidget(similar_title)

        self._similar_container = QWidget()
        self._similar_layout = QVBoxLayout(self._similar_container)
        self._similar_layout.setContentsMargins(0, 2, 0, 0)
        self._similar_layout.setSpacing(3)
        self._similar_placeholder = QLabel("Kein Track ausgewählt")
        self._similar_placeholder.setObjectName("MutedLabel")
        self._similar_layout.addWidget(self._similar_placeholder)
        scroll_layout.addWidget(self._similar_container)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # ── Audio-Player ──
        player_frame = QFrame()
        player_frame.setObjectName("StatsBar")
        player_layout = QVBoxLayout(player_frame)
        player_layout.setContentsMargins(8, 6, 8, 6)
        player_layout.setSpacing(4)

        # Buttons: Play/Stop
        controls = QHBoxLayout()
        controls.setSpacing(6)

        self._btn_play = QPushButton("\u25b6  Play")
        self._btn_play.setFixedWidth(80)
        self._btn_play.setEnabled(False)
        self._btn_play.clicked.connect(self._on_play_pause)
        controls.addWidget(self._btn_play)

        self._btn_stop = QPushButton("\u25a0  Stop")
        self._btn_stop.setFixedWidth(80)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)
        controls.addWidget(self._btn_stop)

        controls.addStretch()

        # Zeitanzeige
        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setObjectName("MutedLabel")
        controls.addWidget(self._time_label)

        player_layout.addLayout(controls)

        # Seek-Slider
        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.setEnabled(False)
        self._seek_slider.sliderPressed.connect(self._on_slider_pressed)
        self._seek_slider.sliderReleased.connect(self._on_slider_released)
        self._seek_slider.sliderMoved.connect(self._on_slider_moved)
        player_layout.addWidget(self._seek_slider)

        main_layout.addWidget(player_frame)

        self.setWidget(container)

    def _setup_player(self) -> None:
        """Initialisiert QMediaPlayer und QAudioOutput."""
        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(0.75)

        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio_output)

        # Signale verbinden
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)

    # ── Public API ───────────────────────────────────────────────────

    def set_result(self, result: AnalysisResult) -> None:
        """
        Zeigt die technischen Daten eines Analyse-Ergebnisses an.

        Aktualisiert alle Felder, Waveform und lädt die Audio-Datei.
        """
        # Vorherige Wiedergabe stoppen
        self._player.stop()
        self._current_result = result

        # Track-Info
        self._track_label.setText(result.file)

        if result.is_error:
            self._rating_label.setText(f"\u274c Fehler: {result.error}")
            self._clear_info_fields()
            self._waveform.clear()
            self._btn_play.setEnabled(False)
            self._btn_stop.setEnabled(False)
            self._seek_slider.setEnabled(False)
            return

        # Rating-Zeile
        rating_colors = {"hit": "#22c55e", "mid": "#eab308", "flop": "#ef4444"}
        color = rating_colors.get(result.rating, "#a5a5a5")
        hit_pct = result.probabilities.get("hit", 0.0)

        self._rating_label.setText(
            f"{result.rating.upper()} | "
            f"Hit: {hit_pct:.1%} | "
            f"Konfidenz: {result.confidence:.1%}"
        )
        self._rating_label.setStyleSheet(f"color: {color}; font-size: 12px;")

        # Audio-Info Felder füllen
        self._populate_info_fields(result.audio_info)

        # Waveform
        if result._waveform is not None:
            self._waveform.set_waveform(result._waveform)
        else:
            self._waveform.clear()

        # Audio-Datei laden
        audio_path = Path(result.path)
        if audio_path.exists():
            self._player.setSource(QUrl.fromLocalFile(str(audio_path)))
            self._btn_play.setEnabled(True)
            self._btn_stop.setEnabled(True)
            self._seek_slider.setEnabled(True)
        else:
            self._btn_play.setEnabled(False)
            self._btn_stop.setEnabled(False)
            self._seek_slider.setEnabled(False)

    def clear(self) -> None:
        """Setzt das Panel auf den Ausgangszustand zurück."""
        self._player.stop()
        self._player.setSource(QUrl())
        self._current_result = None
        self._track_label.setText("Kein Track ausgewählt")
        self._rating_label.setText("")
        self._rating_label.setStyleSheet("")
        self._clear_info_fields()
        self._waveform.clear()
        self.set_similar([])
        self._btn_play.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._seek_slider.setEnabled(False)
        self._seek_slider.setRange(0, 0)
        self._time_label.setText("0:00 / 0:00")

    # ── Audio-Info Felder ────────────────────────────────────────────

    def set_similar(self, similar: list) -> None:
        """
        Zeigt die Liste ähnlicher Tracks an.

        Args:
            similar: [(AnalysisResult, float)] — absteigend nach Similarity-Score.
                     Leere Liste oder [] wenn kein Embedding verfügbar.
        """
        # Alte Einträge entfernen
        while self._similar_layout.count():
            item = self._similar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not similar:
            lbl = QLabel("Kein Embedding verfügbar\n(Track vor dieser Session analysiert?)")
            lbl.setObjectName("MutedLabel")
            lbl.setWordWrap(True)
            self._similar_layout.addWidget(lbl)
            return

        rating_colors = {"hit": "#22c55e", "mid": "#eab308", "flop": "#ef4444"}

        for result, score in similar:
            row = QHBoxLayout()
            row.setSpacing(6)

            # Dateiname (ohne Extension, gekürzt)
            name = result.file
            if len(name) > 32:
                name = name[:29] + "…"
            name_lbl = QLabel(name)
            name_lbl.setToolTip(result.path)
            row.addWidget(name_lbl, stretch=1)

            # Rating-Pill
            color = rating_colors.get(result.rating, "#a5a5a5")
            rating_lbl = QLabel(result.rating.upper())
            rating_lbl.setStyleSheet(
                f"color: {color}; font-size: 10px; font-weight: bold;"
            )
            rating_lbl.setFixedWidth(34)
            row.addWidget(rating_lbl)

            # Similarity-Score
            score_lbl = QLabel(f"{score:.0%}")
            score_lbl.setObjectName("MutedLabel")
            score_lbl.setFixedWidth(36)
            score_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(score_lbl)

            container = QWidget()
            container.setLayout(row)
            self._similar_layout.addWidget(container)

    def _populate_info_fields(self, audio_info: AudioInfo | None) -> None:
        """Füllt die Formular-Felder mit AudioInfo-Daten."""
        if audio_info is None:
            self._clear_info_fields()
            return

        ai = audio_info

        self._info_fields["duration"].setText(ai.duration_formatted)
        self._info_fields["format"].setText(ai.format.upper() if ai.format else "\u2014")
        self._info_fields["sample_rate"].setText(
            f"{ai.sample_rate:,} Hz" if ai.sample_rate else "\u2014"
        )
        self._info_fields["channels"].setText(ai.channels_label if ai.channels else "\u2014")
        self._info_fields["bitrate"].setText(
            f"{ai.bitrate} kbps" if ai.bitrate else "\u2014"
        )
        self._info_fields["file_size"].setText(ai.file_size_formatted)
        self._info_fields["bpm"].setText(
            f"{ai.bpm:.1f}" if ai.bpm else "\u2014"
        )
        self._info_fields["lufs"].setText(
            f"{ai.lufs:.1f} dB" if ai.lufs is not None else "\u2014"
        )
        self._info_fields["key"].setText(ai.key if ai.key else "\u2014")
        self._info_fields["spectral_centroid"].setText(
            f"{ai.spectral_centroid:.0f} Hz" if ai.spectral_centroid is not None else "\u2014"
        )
        self._info_fields["spectral_flatness"].setText(
            f"{ai.spectral_flatness:.4f}" if ai.spectral_flatness is not None else "\u2014"
        )
        self._info_fields["onset_rate"].setText(
            f"{ai.onset_rate:.2f} /s" if ai.onset_rate is not None else "\u2014"
        )

    def _clear_info_fields(self) -> None:
        """Setzt alle Info-Felder auf Platzhalter zurück."""
        for label in self._info_fields.values():
            label.setText("\u2014")

    # ── Player-Steuerung ─────────────────────────────────────────────

    def _on_play_pause(self) -> None:
        """Play/Pause umschalten."""
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_stop(self) -> None:
        """Wiedergabe stoppen."""
        self._player.stop()
        self._waveform.set_playback_position(0.0)

    @Slot(int)
    def _on_position_changed(self, position_ms: int) -> None:
        """Position hat sich geändert (ms)."""
        if not self._is_seeking:
            self._seek_slider.setValue(position_ms)

        # Zeitanzeige aktualisieren
        duration_ms = self._player.duration()
        self._time_label.setText(
            f"{self._format_time(position_ms)} / {self._format_time(duration_ms)}"
        )

        # Waveform-Position aktualisieren
        if duration_ms > 0:
            self._waveform.set_playback_position(position_ms / duration_ms)

    @Slot(int)
    def _on_duration_changed(self, duration_ms: int) -> None:
        """Dauer der Mediendatei bekannt."""
        self._seek_slider.setRange(0, duration_ms)

    @Slot(QMediaPlayer.PlaybackState)
    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        """Playback-Status hat sich geändert."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._btn_play.setText("\u23f8  Pause")
        else:
            self._btn_play.setText("\u25b6  Play")

        if state == QMediaPlayer.PlaybackState.StoppedState:
            self._waveform.set_playback_position(0.0)

    # ── Slider-Events ────────────────────────────────────────────────

    def _on_slider_pressed(self) -> None:
        """Benutzer greift den Slider — Feedback-Loop verhindern."""
        self._is_seeking = True

    def _on_slider_released(self) -> None:
        """Benutzer lässt den Slider los — Position setzen."""
        self._is_seeking = False
        self._player.setPosition(self._seek_slider.value())

    def _on_slider_moved(self, value: int) -> None:
        """Slider wird bewegt — Zeitanzeige aktualisieren."""
        duration_ms = self._player.duration()
        self._time_label.setText(
            f"{self._format_time(value)} / {self._format_time(duration_ms)}"
        )

    def _on_waveform_clicked(self, rel_position: float) -> None:
        """Klick auf die Waveform — Position setzen."""
        duration_ms = self._player.duration()
        if duration_ms > 0:
            self._player.setPosition(int(rel_position * duration_ms))

    # ── Hilfsfunktionen ──────────────────────────────────────────────

    @staticmethod
    def _format_time(ms: int) -> str:
        """Formatiert Millisekunden als M:SS."""
        if ms <= 0:
            return "0:00"
        total_sec = ms // 1000
        minutes = total_sec // 60
        seconds = total_sec % 60
        return f"{minutes}:{seconds:02d}"
