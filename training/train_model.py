"""
train_model.py
==============
Trainiert einen XGBoost-Klassifikator auf MERT-Embeddings + Rank-Labels.

Input: 
  - embeddings/embeddings.npy (MERT-Embeddings)
  - embeddings/embeddings_meta.csv (Track-IDs, Cluster)
  - scout_results_deezer/scouted_tracks.csv (Rank-Labels)

Output:
  - models/spotilyzer_model.joblib (trainiertes Modell)
  - models/training_report.json (Metriken, Confusion Matrix)

Autor: Claude Opus (für Andreas Vogelsang)
Datum: 2026-03-02
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    classification_report, 
    confusion_matrix, 
    accuracy_score,
    f1_score,
    balanced_accuracy_score
)
import xgboost as xgb
import joblib

# ══════════════════════════════════════════════════════════════════════════════
# KONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_EMBEDDINGS_DIR = "embeddings"
DEFAULT_TRACKS_CSV = "scout_results_deezer/scouted_tracks.csv"
DEFAULT_OUTPUT_DIR = "models"

# Rank-Schwellen für Hit/Mid/Flop (aus Scouting-Script)
RANK_THRESHOLDS = {"flop": 300000, "mid": 700000}

# XGBoost Hyperparameter
XGB_PARAMS = {
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "gamma": 0.1,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "objective": "multi:softprob",
    "eval_metric": "mlogloss",
    "tree_method": "hist",  # Schneller, GPU-fähig
    "random_state": 42,
    "n_jobs": -1,
}


# ══════════════════════════════════════════════════════════════════════════════
# DATEN-VORBEREITUNG
# ══════════════════════════════════════════════════════════════════════════════

def rank_to_label(rank: int) -> str:
    """Konvertiert Deezer-Rank zu Hit/Mid/Flop Label."""
    if rank > RANK_THRESHOLDS["mid"]:
        return "hit"
    elif rank >= RANK_THRESHOLDS["flop"]:
        return "mid"
    else:
        return "flop"


def load_data(
    embeddings_dir: Path,
    tracks_csv: Path
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """
    Lädt Embeddings und merged sie mit Rank-Labels.
    
    Returns:
        (X, y, metadata_df)
        X: Embeddings [n_samples, 768]
        y: Labels [n_samples] (encoded)
        metadata_df: DataFrame mit allen Infos
    """
    print("  Lade Embeddings...")
    embeddings = np.load(embeddings_dir / "embeddings.npy")
    meta_df = pd.read_csv(embeddings_dir / "embeddings_meta.csv")
    
    print(f"    Embeddings: {embeddings.shape}")
    print(f"    Metadaten:  {len(meta_df)} Einträge")
    
    print("  Lade Track-Daten...")
    tracks_df = pd.read_csv(tracks_csv)
    print(f"    Tracks: {len(tracks_df)} Einträge")
    
    # Merge: Embeddings-Meta mit Track-Daten (für Rank)
    merged = meta_df.merge(
        tracks_df[["track_id", "rank", "cluster"]],
        on="track_id",
        how="left",
        suffixes=("", "_track")
    )
    
    # Fehlende Ranks droppen
    before = len(merged)
    merged = merged.dropna(subset=["rank"])
    after = len(merged)
    if before != after:
        print(f"    ⚠ {before - after} Tracks ohne Rank entfernt")
    
    # Labels erstellen
    merged["label"] = merged["rank"].apply(rank_to_label)
    
    # Embeddings entsprechend filtern
    valid_indices = merged["embedding_idx"].values
    X = embeddings[valid_indices]
    
    # Label-Encoding
    label_encoder = LabelEncoder()
    label_encoder.fit(["flop", "mid", "hit"])  # Feste Reihenfolge
    y = label_encoder.transform(merged["label"].values)
    
    print(f"\n  Label-Verteilung:")
    for label in ["flop", "mid", "hit"]:
        count = (merged["label"] == label).sum()
        pct = 100 * count / len(merged)
        print(f"    {label:5}: {count:>5} ({pct:.1f}%)")
    
    return X, y, merged, label_encoder


# ══════════════════════════════════════════════════════════════════════════════
# TRAINING
# ══════════════════════════════════════════════════════════════════════════════

def train_model(
    X: np.ndarray,
    y: np.ndarray,
    use_gpu: bool = False,
    test_size: float = 0.2
) -> tuple[xgb.XGBClassifier, dict]:
    """
    Trainiert XGBoost-Modell mit Train/Test-Split und Cross-Validation.
    
    Returns:
        (model, metrics_dict)
    """
    print(f"\n  Train/Test Split ({int((1-test_size)*100)}/{int(test_size*100)})...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, 
        test_size=test_size, 
        random_state=42,
        stratify=y
    )
    print(f"    Train: {len(X_train)}, Test: {len(X_test)}")
    
    # Model konfigurieren
    params = XGB_PARAMS.copy()
    if use_gpu:
        params["device"] = "cuda"
        print("  Training auf GPU...")
    else:
        print("  Training auf CPU...")
    
    model = xgb.XGBClassifier(**params)
    
    # Training mit Early Stopping
    print("  Trainiere XGBoost...")
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )
    
    # Predictions
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)
    
    # Metriken berechnen
    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_test, y_pred),
        "f1_macro": f1_score(y_test, y_pred, average="macro"),
        "f1_weighted": f1_score(y_test, y_pred, average="weighted"),
    }
    
    # Confusion Matrix
    cm = confusion_matrix(y_test, y_pred)
    metrics["confusion_matrix"] = cm.tolist()
    
    # Per-Class Metrics
    report = classification_report(y_test, y_pred, target_names=["flop", "mid", "hit"], output_dict=True)
    metrics["per_class"] = {
        "flop": {"precision": report["flop"]["precision"], "recall": report["flop"]["recall"], "f1": report["flop"]["f1-score"]},
        "mid": {"precision": report["mid"]["precision"], "recall": report["mid"]["recall"], "f1": report["mid"]["f1-score"]},
        "hit": {"precision": report["hit"]["precision"], "recall": report["hit"]["recall"], "f1": report["hit"]["f1-score"]},
    }
    
    # Cross-Validation Score
    print("  Cross-Validation (5-fold)...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X, y, cv=cv, scoring="balanced_accuracy")
    metrics["cv_balanced_accuracy_mean"] = cv_scores.mean()
    metrics["cv_balanced_accuracy_std"] = cv_scores.std()
    
    return model, metrics


# ══════════════════════════════════════════════════════════════════════════════
# REPORTING
# ══════════════════════════════════════════════════════════════════════════════

def print_report(metrics: dict, label_encoder):
    """Gibt einen formatierten Trainingsreport aus."""
    
    print(f"\n{'═'*79}")
    print(f"  TRAINING REPORT")
    print(f"{'═'*79}")
    
    print(f"\n  Overall Metrics:")
    print(f"    Accuracy:          {metrics['accuracy']:.3f}")
    print(f"    Balanced Accuracy: {metrics['balanced_accuracy']:.3f}")
    print(f"    F1 (macro):        {metrics['f1_macro']:.3f}")
    print(f"    F1 (weighted):     {metrics['f1_weighted']:.3f}")
    
    print(f"\n  Cross-Validation (5-fold):")
    print(f"    Balanced Accuracy: {metrics['cv_balanced_accuracy_mean']:.3f} ± {metrics['cv_balanced_accuracy_std']:.3f}")
    
    print(f"\n  Per-Class Performance:")
    print(f"    {'Class':8} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print(f"    {'-'*38}")
    for cls in ["flop", "mid", "hit"]:
        m = metrics["per_class"][cls]
        print(f"    {cls:8} {m['precision']:>10.3f} {m['recall']:>10.3f} {m['f1']:>10.3f}")
    
    print(f"\n  Confusion Matrix:")
    print(f"    {'':8} {'flop':>8} {'mid':>8} {'hit':>8}  ← predicted")
    cm = metrics["confusion_matrix"]
    for i, cls in enumerate(["flop", "mid", "hit"]):
        row = "    "
        row += f"{cls:8}"
        for j in range(3):
            row += f" {cm[i][j]:>7}"
        print(row)
    print(f"    ↑ actual")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Trainiere XGBoost-Klassifikator auf MERT-Embeddings"
    )
    parser.add_argument(
        "--embeddings-dir",
        default=DEFAULT_EMBEDDINGS_DIR,
        help=f"Verzeichnis mit Embeddings (default: {DEFAULT_EMBEDDINGS_DIR})"
    )
    parser.add_argument(
        "--tracks-csv",
        default=DEFAULT_TRACKS_CSV,
        help=f"CSV mit Track-Daten und Ranks (default: {DEFAULT_TRACKS_CSV})"
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output-Verzeichnis für Modell (default: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="GPU für XGBoost verwenden"
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Test-Set Größe (default: 0.2)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur Daten laden, nicht trainieren"
    )
    args = parser.parse_args()

    print(f"═══════════════════════════════════════════════════════════════════════════════")
    print(f"  SPOTILYZER MODEL TRAINING")
    print(f"═══════════════════════════════════════════════════════════════════════════════")
    
    embeddings_dir = Path(args.embeddings_dir)
    tracks_csv = Path(args.tracks_csv)
    output_dir = Path(args.output_dir)
    
    # Prüfen ob Dateien existieren
    if not (embeddings_dir / "embeddings.npy").exists():
        print(f"  Fehler: Embeddings nicht gefunden: {embeddings_dir / 'embeddings.npy'}")
        print(f"  → Erst 'python extract_embeddings.py' ausführen!")
        sys.exit(1)
    
    if not tracks_csv.exists():
        print(f"  Fehler: Track-CSV nicht gefunden: {tracks_csv}")
        sys.exit(1)
    
    # Daten laden
    print(f"\n{'─'*79}")
    print(f"  DATEN LADEN")
    print(f"{'─'*79}")
    
    X, y, meta_df, label_encoder = load_data(embeddings_dir, tracks_csv)
    
    print(f"\n  Dataset:")
    print(f"    Features:  {X.shape[1]} (MERT embedding dim)")
    print(f"    Samples:   {X.shape[0]}")
    print(f"    Classes:   {len(label_encoder.classes_)} ({', '.join(label_encoder.classes_)})")
    
    if args.dry_run:
        print(f"\n  [DRY RUN] Training übersprungen.")
        return
    
    # Training
    print(f"\n{'─'*79}")
    print(f"  TRAINING")
    print(f"{'─'*79}")
    
    model, metrics = train_model(X, y, use_gpu=args.gpu, test_size=args.test_size)
    
    # Report ausgeben
    print_report(metrics, label_encoder)
    
    # Modell speichern
    output_dir.mkdir(parents=True, exist_ok=True)
    
    model_path = output_dir / "spotilyzer_model.joblib"
    joblib.dump({
        "model": model,
        "label_encoder": label_encoder,
        "rank_thresholds": RANK_THRESHOLDS,
        "embedding_dim": X.shape[1],
    }, model_path)
    print(f"\n  Modell gespeichert: {model_path}")
    
    # Report speichern
    report = {
        "created": datetime.now().isoformat(),
        "dataset": {
            "n_samples": X.shape[0],
            "n_features": X.shape[1],
            "label_distribution": meta_df["label"].value_counts().to_dict(),
        },
        "model": {
            "type": "XGBClassifier",
            "params": XGB_PARAMS,
        },
        "metrics": metrics,
        "rank_thresholds": RANK_THRESHOLDS,
    }
    
    report_path = output_dir / "training_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"  Report gespeichert: {report_path}")
    
    print(f"\n{'─'*79}")
    print(f"  DONE")
    print(f"{'─'*79}")
    print(f"\n  Nächster Schritt:")
    print(f"    python analyze_track.py <dein_track.mp3>")


if __name__ == "__main__":
    main()
