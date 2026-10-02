"""Automated model selection (item: measured comparison, not a hard-coded favorite).

Pipeline: dataset analysis -> candidate models -> stratified k-fold CV
    -> evaluation -> ranked comparison -> measured winner.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.naive_bayes import GaussianNB
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from backend.app.core.logging import get_logger
from backend.app.ml.data.synthetic import generate_flow_dataset

logger = get_logger(__name__)

# Candidate set — every candidate is measured; the winner is chosen by CV score.
CANDIDATES: Dict[str, Any] = {
    "logistic_regression": lambda seed: make_pipeline(
        StandardScaler(), LogisticRegression(max_iter=500, random_state=seed)
    ),
    "random_forest": lambda seed: RandomForestClassifier(
        n_estimators=50, max_depth=8, random_state=seed
    ),
    "gaussian_nb": lambda seed: GaussianNB(),
    "gradient_boosting": lambda seed: GradientBoostingClassifier(
        n_estimators=30, max_depth=3, random_state=seed
    ),
    "svm_rbf": lambda seed: make_pipeline(
        StandardScaler(), SVC(kernel="rbf", probability=True, random_state=seed)
    ),
}

SCORING = ("f1_macro", "precision_macro", "recall_macro", "roc_auc")


def analyze_dataset(df, target_column: str = "label") -> Dict[str, Any]:
    """Cheap dataset statistics that inform (but do not dictate) candidates."""
    from collections import Counter
    y = df[target_column]
    counts = Counter(y.tolist())
    n = len(y)
    imbalance = max(counts.values()) / n if n else 0.0
    numeric_cols = [c for c in df.columns if c != target_column]
    missing = int(df[numeric_cols].isna().sum().sum())
    return {
        "n_samples": n,
        "n_features": len(numeric_cols),
        "class_distribution": {str(k): v for k, v in counts.items()},
        "imbalance_ratio": round(imbalance, 4),
        "missing_cells": missing,
        "high_imbalance": imbalance > 0.8,
        "analysis_note": (
            "Candidates below are all evaluated; selection is by cross-validation, "
            "not by heuristic."
        ),
    }


def select_model(
    dataset=None,
    target_column: str = "label",
    candidates: Optional[List[str]] = None,
    cv_folds: int = 5,
    seed: int = 42,
    n_samples: int = 800,
) -> Dict[str, Any]:
    """Run stratified k-fold CV across the candidate set and rank them."""
    if dataset is None:
        dataset = generate_flow_dataset(n_samples=n_samples, random_state=seed)
    df = dataset.dropna()
    if target_column not in df.columns:
        raise ValueError(
            f"Target column '{target_column}' not in dataset "
            f"(columns: {', '.join(map(str, df.columns))})."
        )

    selected = list(candidates or CANDIDATES.keys())
    for name in selected:
        if name not in CANDIDATES:
            raise ValueError(
                f"Unknown candidate '{name}'. Available: {', '.join(CANDIDATES)}."
            )

    y = df[target_column].values
    X = df[[c for c in df.columns if c != target_column]].values
    classes = np.unique(y)
    if len(classes) < 2:
        found = str(classes[0]) if len(classes) else "empty"
        raise ValueError(
            f"Dataset has a single class ({found}); stratified cross-validation "
            "requires at least two classes."
        )
    min_class_count = int(np.bincount(y.astype(int)).min())
    if min_class_count < 2:
        raise ValueError(
            "Each class needs at least 2 samples for stratified cross-validation "
            f"(smallest class has {min_class_count})."
        )
    effective_folds = max(2, min(cv_folds, min_class_count))

    analysis = analyze_dataset(df, target_column)
    rows: List[Dict[str, Any]] = []

    for name in selected:
        model = CANDIDATES[name](seed)
        t0 = time.perf_counter()
        try:
            cv = StratifiedKFold(n_splits=effective_folds, shuffle=True, random_state=seed)
            scores = cross_validate(
                model, X, y, cv=cv, scoring=list(SCORING),
                error_score="raise", return_train_score=False,
            )
            elapsed = (time.perf_counter() - t0) * 1000.0
            row: Dict[str, Any] = {
                "model": name,
                "status": "evaluated",
                "fit_time_ms_mean": round(float(np.mean(scores["fit_time"]) * 1000), 3),
                "score_time_ms_mean": round(float(np.mean(scores["score_time"]) * 1000), 3),
                "total_cv_time_ms": round(elapsed, 3),
            }
            for metric in SCORING:
                key = f"test_{metric}"
                vals = scores.get(key, [])
                row[metric] = round(float(np.mean(vals)), 6) if len(vals) else None
                row[f"{metric}_std"] = round(float(np.std(vals)), 6) if len(vals) else None
        except Exception as exc:
            logger.warning("Candidate %s failed CV: %s", name, exc)
            row = {"model": name, "status": "failed", "error": str(exc)}
        rows.append(row)

    evaluated = [r for r in rows if r.get("status") == "evaluated" and r.get("f1_macro") is not None]
    evaluated.sort(key=lambda r: (-r["f1_macro"], r["model"]))
    winner = evaluated[0]["model"] if evaluated else None

    margin = None
    if len(evaluated) >= 2:
        margin = round(evaluated[0]["f1_macro"] - evaluated[1]["f1_macro"], 6)

    return {
        "dataset_analysis": analysis,
        "cv_folds": effective_folds,
        "cv_requested_folds": cv_folds,
        "scoring": list(SCORING),
        "candidates": rows,
        "ranking": [r["model"] for r in evaluated],
        "selected_model": winner,
        "selection_margin_f1_macro": margin,
        "selection_rule": "highest mean stratified-k-fold macro-F1 across all candidates",
        "seed": seed,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "COMPLETED",
    }
