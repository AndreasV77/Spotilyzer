"""
Embedding-basierte Ähnlichkeitssuche ("Sounds like ...").

Vergleicht MERT-Embeddings (1024-dim) via Cosine-Similarity.
Eingang: ein Query-Track + Liste aller Kandidaten aus der aktuellen Session.
Ausgang: Top-N ähnlichste Tracks mit Similarity-Score (0.0–1.0).

Cosine-Similarity misst den Winkel zwischen Embedding-Vektoren, nicht die
euklidische Distanz. Das ist robuster gegenüber unterschiedlichen
Lautstärken/Masteringleveln: zwei gleichklingende Songs haben nahezu
identische Cosine-Similarity, auch wenn ihre Amplituden abweichen.

Einschränkung: _embedding ist session-only und nicht persistiert.
Tracks aus importierten JSON-Sessions haben kein Embedding (→ werden
übersprungen).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from spotilyzer.data.models import AnalysisResult


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine-Similarity zwischen zwei Vektoren (0.0 = entgegengesetzt,
    1.0 = identisch).

    Gibt 0.0 zurück wenn einer der Vektoren die Norm 0 hat (Nullvektor).
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def find_similar(
    query: "AnalysisResult",
    candidates: list["AnalysisResult"],
    top_n: int = 5,
    min_similarity: float = 0.0,
) -> list[tuple["AnalysisResult", float]]:
    """
    Findet die ähnlichsten Tracks zum Query-Track.

    Args:
        query:          Referenz-Track (muss _embedding haben).
        candidates:     Alle Tracks aus der Session.
        top_n:          Maximale Anzahl Ergebnisse.
        min_similarity: Mindestschwelle (0.0–1.0); Tracks darunter werden
                        nicht zurückgegeben.

    Returns:
        Liste von (AnalysisResult, similarity_score), absteigend nach Score.
        Leer wenn query._embedding None ist oder zu wenig Kandidaten.
    """
    if query._embedding is None:
        return []

    scored: list[tuple["AnalysisResult", float]] = []

    for candidate in candidates:
        # Query selbst überspringen
        if candidate.path == query.path:
            continue
        # Tracks ohne Embedding überspringen (aus JSON-Import)
        if candidate._embedding is None:
            continue
        # Fehlerhafte Tracks überspringen
        if candidate.is_error:
            continue

        sim = cosine_similarity(query._embedding, candidate._embedding)
        if sim >= min_similarity:
            scored.append((candidate, sim))

    # Absteigend nach Similarity sortieren, Top-N zurückgeben
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]
