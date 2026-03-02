"""
AnalysisPipeline - Orchestriert Embedder + Predictor + AudioInfo.

Hauptschnittstelle für GUI und CLI.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from spotilyzer.core.embedder import MERTEmbedder
from spotilyzer.core.predictor import SpotilyzerPredictor
from spotilyzer.core.audio_info import extract_audio_info, extract_waveform_display
from spotilyzer.data.models import AnalysisResult, ModelInfo


class AnalysisPipeline:
    """
    Orchestriert die komplette Analyse-Pipeline:
    Audio → MERT-Embedding → XGBoost-Prediction → AnalysisResult.

    Usage:
        pipeline = AnalysisPipeline(Path("models/spotilyzer_model.joblib"))
        result = pipeline.analyze(Path("track.mp3"))
    """

    def __init__(
        self,
        model_path: Path,
        device: str = "auto",
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialisiert die Pipeline.

        Args:
            model_path: Pfad zum trainierten XGBoost-Modell (.joblib).
            device: "cuda", "cpu" oder "auto" (auto-detect).
            progress_callback: Optional, wird mit Status-Strings aufgerufen.
        """
        self._notify = progress_callback or (lambda msg: None)
        self.model_path = model_path

        self._notify("Lade Spotilyzer-Modell...")
        self.predictor = SpotilyzerPredictor(model_path)

        self._notify("Lade MERT-Embedder...")
        self.embedder = MERTEmbedder.get_instance(
            device=device, progress_callback=progress_callback
        )

        # Model-Info für Vergleichbarkeit vorbereiten
        self._model_info = self._build_model_info()

        self._notify("Pipeline bereit!")

    def _build_model_info(self) -> ModelInfo:
        """Erstellt ModelInfo aus den aktuellen Pipeline-Parametern."""
        training_date = None
        dataset_info = None

        # Training-Report lesen (falls vorhanden)
        report_path = self.model_path.parent / "training_report.json"
        if report_path.exists():
            try:
                import json
                with open(report_path, "r", encoding="utf-8") as f:
                    report = json.load(f)
                training_date = report.get("timestamp", report.get("date"))
                dataset_info = report.get("dataset_info")
                if not dataset_info:
                    # Aus Trainings-Metriken zusammenbauen
                    n_samples = report.get("total_samples") or report.get("n_samples")
                    if n_samples:
                        dataset_info = f"{n_samples} Samples"
            except Exception:
                pass

        return ModelInfo(
            model_name=self.model_path.name,
            model_path=str(self.model_path),
            embedder="MERT-v1-95M",
            device=self.embedder.device,
            training_date=training_date,
            dataset_info=dataset_info,
        )

    @property
    def model_info(self) -> ModelInfo:
        """Aktuelle Model-Info."""
        return self._model_info

    @property
    def device(self) -> str:
        """Aktuelles Device (cuda/cpu)."""
        return self.embedder.device

    @property
    def device_display(self) -> str:
        """Device-Name für Anzeige."""
        if self.device == "cuda":
            try:
                import torch
                name = torch.cuda.get_device_name(0)
                return f"CUDA ({name})"
            except Exception:
                return "CUDA"
        return "CPU"

    def analyze(
        self,
        filepath: Path,
        include_audio_info: bool = True,
        include_waveform: bool = False,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> AnalysisResult:
        """
        Analysiert eine einzelne Audio-Datei.

        Args:
            filepath: Pfad zur Audio-Datei.
            include_audio_info: Technische Metadaten extrahieren?
            include_waveform: Waveform für Visualisierung extrahieren?
            progress_callback: Optional, für detaillierte Status-Updates.

        Returns:
            AnalysisResult mit Rating, Confidence, Probabilities und optional AudioInfo.
        """
        notify = progress_callback or self._notify
        filepath = Path(filepath)
        timestamp = datetime.now().isoformat()

        try:
            # 1. Embedding extrahieren
            notify(f"Extrahiere Embedding: {filepath.name}...")
            embedding = self.embedder.process_file(filepath)

            # 2. Prediction
            notify(f"Analysiere: {filepath.name}...")
            probabilities, rating, confidence = self.predictor.predict(embedding)

            # 3. Audio-Info (optional)
            audio_info = None
            if include_audio_info:
                notify(f"Technische Daten: {filepath.name}...")
                audio_info = extract_audio_info(filepath)

            # 4. Waveform (optional)
            waveform = None
            if include_waveform:
                waveform = extract_waveform_display(filepath)

            result = AnalysisResult(
                file=filepath.name,
                path=str(filepath),
                timestamp=timestamp,
                rating=rating,
                confidence=confidence,
                probabilities=probabilities,
                audio_info=audio_info,
                model_info=self._model_info,
            )
            result._waveform = waveform
            return result

        except Exception as e:
            return AnalysisResult(
                file=filepath.name,
                path=str(filepath),
                timestamp=timestamp,
                error=str(e),
            )

    def analyze_batch(
        self,
        files: list[Path],
        include_audio_info: bool = True,
        include_waveform: bool = False,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> list[AnalysisResult]:
        """
        Batch-Analyse mehrerer Dateien.

        Args:
            files: Liste von Pfaden zu Audio-Dateien.
            include_audio_info: Technische Metadaten extrahieren?
            include_waveform: Waveform für Visualisierung extrahieren?
            progress_callback: Optional, callback(message, current_index, total).
            cancel_check: Optional, gibt True zurück wenn abgebrochen werden soll.

        Returns:
            Liste von AnalysisResult (gleiche Reihenfolge wie Input).
        """
        results = []
        total = len(files)

        for i, filepath in enumerate(files):
            # Abbruch prüfen
            if cancel_check and cancel_check():
                break

            if progress_callback:
                progress_callback(
                    f"Analysiere {filepath.name} ({i + 1}/{total})...",
                    i,
                    total,
                )

            result = self.analyze(
                filepath,
                include_audio_info=include_audio_info,
                include_waveform=include_waveform,
            )
            results.append(result)

        return results
