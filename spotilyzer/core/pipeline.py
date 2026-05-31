"""
AnalysisPipeline - Orchestriert Embedder + Predictor + AudioInfo.

Hauptschnittstelle für GUI und CLI.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from spotilyzer.core.embedder import MERTEmbedder
from spotilyzer.core.predictor import SpotilyzerPredictor
from spotilyzer.core.audio_info import extract_audio_info, extract_waveform_display
from spotilyzer.core.clap_analyzer import CLAPAnalyzer
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
        vram_mode: str = "parallel",
    ):
        """
        Initialisiert die Pipeline.

        Args:
            model_path: Pfad zum trainierten XGBoost-Modell (.joblib).
            device: "cuda", "cpu" oder "auto" (auto-detect).
            progress_callback: Optional, wird mit Status-Strings aufgerufen.
            vram_mode: "parallel" (beide Modelle gleichzeitig im VRAM, Standard)
                       oder "sequential" (MERT/CLAP wechseln sich ab, für <8 GB VRAM).
        """
        self._notify = progress_callback or (lambda msg: None)
        self.model_path = model_path
        self.vram_mode = vram_mode

        self._notify("Lade Spotilyzer-Modell...")
        self.predictor = SpotilyzerPredictor(model_path)

        self._notify("Lade MERT-Embedder...")
        self.embedder = MERTEmbedder.get_instance(
            device=device, progress_callback=progress_callback
        )

        # CLAPAnalyzer wird lazy geladen (erst bei erstem include_clap=True Aufruf)
        self._clap: Optional[CLAPAnalyzer] = None
        self._clap_device = self.embedder.device  # gleiches Device wie MERT

        # Model-Info für Vergleichbarkeit vorbereiten
        self._model_info = self._build_model_info()

        self._notify("Pipeline bereit!")

    def _find_report_path(self) -> Path:
        """Finds training_report_*.json next to the model file.

        Strategy: date-tag match first (last _-segment of model stem, e.g.
        '20260529'), then newest glob, then bare-name fallback.
        The date-tag approach handles the _validated suffix asymmetry between
        model and report filenames.
        """
        parent = self.model_path.parent
        date_tag = self.model_path.stem.rsplit("_", 1)[-1]
        if date_tag.isdigit() and len(date_tag) == 8:
            matches = list(parent.glob(f"training_report_*{date_tag}.json"))
            if matches:
                return matches[0]
        candidates = sorted(
            parent.glob("training_report_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0]
        return parent / "training_report.json"

    def _build_model_info(self) -> ModelInfo:
        """Erstellt ModelInfo aus den aktuellen Pipeline-Parametern."""
        training_date = None
        dataset_info = None

        # Training-Report lesen (falls vorhanden)
        report_path = self._find_report_path()
        if report_path.exists():
            try:
                import json
                with open(report_path, "r", encoding="utf-8") as f:
                    report = json.load(f)
                training_date = report.get("created") or report.get("timestamp") or report.get("date")
                dataset_info = report.get("dataset_info")
                if not dataset_info:
                    n_samples = (
                        (report.get("dataset") or {}).get("n_samples")
                        or report.get("total_samples")
                        or report.get("n_samples")
                    )
                    if n_samples:
                        dataset_info = f"{n_samples} Samples"
            except Exception:
                pass

        return ModelInfo(
            model_name=self.model_path.name,
            model_path=str(self.model_path),
            embedder="MERT-v1-330M",
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

    def _get_clap(self, notify: Callable[[str], None]) -> CLAPAnalyzer:
        """Lazy-Loader für CLAPAnalyzer (wird nur bei Bedarf initialisiert)."""
        if self._clap is None:
            notify("Lade CLAP-Modell...")
            self._clap = CLAPAnalyzer.get_instance(
                device=self._clap_device,
                progress_callback=notify,
            )
        return self._clap

    def analyze(
        self,
        filepath: Path,
        include_audio_info: bool = True,
        include_waveform: bool = False,
        include_clap: bool = False,
        clap_tag_sets: Optional[dict] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> AnalysisResult:
        """
        Analysiert eine einzelne Audio-Datei.

        Args:
            filepath: Pfad zur Audio-Datei.
            include_audio_info: Technische Metadaten extrahieren?
            include_waveform: Waveform für Visualisierung extrahieren?
            include_clap: Zero-Shot Genre/Mood-Analyse via LAION CLAP?
            clap_tag_sets: Eigene Tag-Sets für CLAP. None = DEFAULT_TAG_SETS.
            progress_callback: Optional, für detaillierte Status-Updates.

        Returns:
            AnalysisResult mit Rating, Confidence, Probabilities und optional
            AudioInfo und CLAPResult.
        """
        notify = progress_callback or self._notify
        filepath = Path(filepath)
        timestamp = datetime.now().isoformat()

        try:
            # 1. Embeddings extrahieren (MERT, ein Embedding pro 30s-Chunk)
            notify(f"Extrahiere Embeddings: {filepath.name}...")
            chunk_embeddings = self.embedder.process_file_chunks(filepath)

            # 2. Prediction (XGBoost pro Chunk, mean der Wahrscheinlichkeiten)
            notify(f"Analysiere: {filepath.name}...")
            probabilities, rating, confidence = self.predictor.predict_chunks(chunk_embeddings)
            # Mean-pooled Embedding für Similarity-Suche ("Sounds like ...")
            track_embedding = np.mean(chunk_embeddings, axis=0)

            # 3. Audio-Info (optional)
            audio_info = None
            if include_audio_info:
                notify(f"Technische Daten: {filepath.name}...")
                audio_info = extract_audio_info(filepath)

            # 4. Waveform (optional)
            waveform = None
            if include_waveform:
                waveform = extract_waveform_display(filepath)

            # 5. CLAP Zero-Shot Analyse (optional)
            clap_result = None
            if include_clap:
                notify(f"CLAP Genre/Mood: {filepath.name}...")
                try:
                    if self.vram_mode == "sequential":
                        # MERT auf CPU → CLAP auf GPU → MERT wird beim nächsten
                        # process_file()-Aufruf via _ensure_on_device() automatisch zurückgeholt
                        self.embedder.offload_to_cpu()
                    clap = self._get_clap(notify)
                    if self.vram_mode == "sequential":
                        clap.restore_to_device()
                    clap_result = clap.analyze(filepath, tag_sets=clap_tag_sets)
                    if self.vram_mode == "sequential":
                        clap.offload_to_cpu()
                except Exception as clap_err:
                    notify(f"CLAP fehlgeschlagen: {clap_err}")

            result = AnalysisResult(
                file=filepath.name,
                path=str(filepath),
                timestamp=timestamp,
                rating=rating,
                confidence=confidence,
                probabilities=probabilities,
                audio_info=audio_info,
                model_info=self._model_info,
                clap_result=clap_result,
            )
            result._waveform = waveform
            result._embedding = track_embedding
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
        include_clap: bool = False,
        clap_tag_sets: Optional[dict] = None,
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
                include_clap=include_clap,
                clap_tag_sets=clap_tag_sets,
            )
            results.append(result)

        return results
