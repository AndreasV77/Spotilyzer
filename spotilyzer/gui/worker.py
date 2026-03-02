"""
QThread-Worker für ML-Inferenz und Audio-Info-Extraktion.

Trennt schwere Berechnungen vom GUI-Thread.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

from spotilyzer.core.pipeline import AnalysisPipeline
from spotilyzer.core.audio_info import extract_waveform_display
from spotilyzer.data.models import AnalysisResult


class PipelineInitWorker(QThread):
    """
    Initialisiert die ML-Pipeline im Hintergrund.

    Signals:
        progress(str): Status-Updates.
        ready(AnalysisPipeline): Pipeline bereit.
        error(str): Fehlermeldung.
    """

    progress = Signal(str)
    ready = Signal(object)  # AnalysisPipeline
    error = Signal(str)

    def __init__(self, model_path: Path, device: str = "auto", parent=None):
        super().__init__(parent)
        self.model_path = model_path
        self.device = device

    def run(self):
        try:
            pipeline = AnalysisPipeline(
                model_path=self.model_path,
                device=self.device,
                progress_callback=lambda msg: self.progress.emit(msg),
            )
            self.ready.emit(pipeline)
        except Exception as e:
            self.error.emit(str(e))


class AnalysisWorker(QThread):
    """
    Führt die ML-Analyse für eine oder mehrere Dateien durch.

    Signals:
        progress(str): Status-Updates.
        result_ready(AnalysisResult): Einzelnes Ergebnis bereit.
        batch_progress(int, int): (current_index, total_count).
        finished_all(): Alle Dateien verarbeitet.
        error(str): Fehlermeldung.
    """

    progress = Signal(str)
    result_ready = Signal(object)  # AnalysisResult
    batch_progress = Signal(int, int)
    finished_all = Signal()
    error = Signal(str)

    def __init__(
        self,
        pipeline: AnalysisPipeline,
        files: list[str],
        include_audio_info: bool = True,
        include_waveform: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.pipeline = pipeline
        self.files = files
        self.include_audio_info = include_audio_info
        self.include_waveform = include_waveform
        self._cancelled = False

    def cancel(self):
        """Bricht die Verarbeitung nach dem aktuellen Track ab."""
        self._cancelled = True

    def run(self):
        total = len(self.files)

        for i, filepath_str in enumerate(self.files):
            if self._cancelled:
                self.progress.emit("Abgebrochen.")
                break

            filepath = Path(filepath_str)
            self.progress.emit(
                f"Analysiere {filepath.name} ({i + 1}/{total})..."
            )
            self.batch_progress.emit(i, total)

            try:
                result = self.pipeline.analyze(
                    filepath,
                    include_audio_info=self.include_audio_info,
                    include_waveform=self.include_waveform,
                )
                self.result_ready.emit(result)
            except Exception as e:
                self.error.emit(f"{filepath.name}: {e}")

        self.batch_progress.emit(total, total)
        self.finished_all.emit()


class WaveformWorker(QThread):
    """
    Extrahiert Waveform-Daten im Hintergrund.

    Signals:
        ready(str, object): (filepath, numpy_array) Waveform bereit.
    """

    ready = Signal(str, object)

    def __init__(self, filepath: str, target_width: int = 800, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.target_width = target_width

    def run(self):
        data = extract_waveform_display(
            Path(self.filepath),
            target_width=self.target_width,
        )
        self.ready.emit(self.filepath, data)
