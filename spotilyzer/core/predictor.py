"""
SpotilyzerPredictor - Wrapper für das trainierte XGBoost-Modell.

Nimmt 768-dim Embeddings entgegen und gibt Hit/Mid/Flop-Bewertungen zurück.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import joblib
import numpy as np

from spotilyzer.data.models import AnalysisResult


class SpotilyzerPredictor:
    """
    Wrapper für das trainierte XGBoost-Modell.

    Lädt ein mit joblib gespeichertes Modell-Dict mit den Keys:
    - "model": Trainiertes XGBoost-Modell
    - "label_encoder": sklearn LabelEncoder (hit/mid/flop)

    Usage:
        predictor = SpotilyzerPredictor(Path("models/spotilyzer_model.joblib"))
        proba, label = predictor.predict(embedding)
    """

    def __init__(self, model_path: Path):
        """
        Lädt das trainierte Modell.

        Args:
            model_path: Pfad zur .joblib Datei.

        Raises:
            FileNotFoundError: Wenn die Datei nicht existiert.
            KeyError: Wenn das Dict nicht die erwarteten Keys hat.
        """
        if not model_path.exists():
            raise FileNotFoundError(
                f"Modell nicht gefunden: {model_path}\n"
                f"Erst 'python training/train_model.py' ausführen!"
            )

        data = joblib.load(model_path)

        if "model" not in data or "label_encoder" not in data:
            raise KeyError(
                f"Ungültiges Modell-Format. Erwartet: 'model' + 'label_encoder' Keys."
            )

        self.model = data["model"]
        self.label_encoder = data["label_encoder"]
        self.classes = list(self.label_encoder.classes_)
        self._model_path = model_path

    @property
    def model_name(self) -> str:
        """Dateiname des geladenen Modells."""
        return self._model_path.name

    def predict(self, embedding: np.ndarray) -> tuple[dict, str, float]:
        """
        Prediction: single embedding → probabilities + label.

        Args:
            embedding: 1024-dim numpy Array.

        Returns:
            Tuple: ({"hit": 0.85, "mid": 0.10, "flop": 0.05}, "hit", 0.85)
        """
        embedding_2d = embedding.reshape(1, -1)
        proba = self.model.predict_proba(embedding_2d)[0]
        pred_idx = int(np.argmax(proba))
        pred_label = self.label_encoder.inverse_transform([pred_idx])[0]
        confidence = float(proba[pred_idx])

        prob_dict = {
            label: float(proba[i])
            for i, label in enumerate(self.label_encoder.classes_)
        }

        return prob_dict, pred_label, confidence

    def predict_chunks(self, embeddings: list[np.ndarray]) -> tuple[dict, str, float]:
        """
        Per-chunk prediction: XGBoost auf jedem Chunk, Mittelwert der Wahrscheinlichkeiten.

        Jeder 30s-Chunk entspricht dem Trainings-Format (Deezer-Preview = 1 Clip).
        Das Averaging passiert auf Wahrscheinlichkeits-Ebene, nicht auf Embedding-Ebene.

        Args:
            embeddings: Liste von 1024-dim Arrays (ein Array pro 30s-Chunk).

        Returns:
            Tuple: (gemittelte probabilities, label, confidence)
        """
        if len(embeddings) == 1:
            return self.predict(embeddings[0])

        all_probs = [self.predict(emb)[0] for emb in embeddings]
        mean_probs = {
            label: float(np.mean([p[label] for p in all_probs]))
            for label in self.label_encoder.classes_
        }

        pred_label = max(mean_probs, key=mean_probs.__getitem__)
        confidence = mean_probs[pred_label]

        return mean_probs, pred_label, confidence
