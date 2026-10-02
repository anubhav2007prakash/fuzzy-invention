"""Differential tests — ML evaluation metrics.

Compares the production metrics engine
(backend.app.ml.evaluation.metrics.compute_metrics) against an independent
reference implementation that computes the same quantities using only
NumPy arithmetic (no sklearn).

This catches silent regressions in precision/recall/F1/accuracy formulas
that could produce misleading performance reports without any exception.

Reference implementation scope
-------------------------------
The reference re-implements only the core scalar metrics that can be
expressed in closed-form arithmetic:
  - accuracy = correct / total
  - precision_macro = mean of per-class precisions
  - recall_macro    = mean of per-class recalls
  - f1_macro        = harmonic mean of per-class F1s

It does NOT replicate probability-based metrics (ROC-AUC, PR-AUC, Brier
score) because those require sorting + integration operations that would
re-implement sklearn non-trivially; those metrics are left out of scope.

Component: metrics
Tests:
  DT-METR-01  Binary: all correct predictions → accuracy=1, F1=1
  DT-METR-02  Binary: all wrong predictions → known degenerate values
  DT-METR-03  Binary: mixed predictions — scalar metrics match reference
  DT-METR-04  Multiclass: 3-class accuracy and macro-F1 match reference
  DT-METR-05  Multiclass: imbalanced dataset — macro-F1 reflects imbalance
  DT-METR-06  Binary: FPR and FNR match reference confusion matrix arithmetic
  DT-METR-07  Determinism: same inputs always produce same outputs
  DT-METR-08  Class distribution proportions sum to 1.0
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pytest

from backend.app.ml.evaluation.metrics import compute_metrics


# ── Reference implementation (numpy-only, no sklearn) ────────────────────────

def _ref_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Reference metric computation using only numpy arithmetic.

    Returns accuracy, precision_macro, recall_macro, f1_macro — exact same
    semantics as sklearn with average='macro', zero_division=0.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    classes = np.unique(y_true)
    total = len(y_true)
    correct = int(np.sum(y_true == y_pred))
    accuracy = correct / total if total > 0 else 0.0

    precisions, recalls, f1s = [], [], []
    for c in classes:
        tp = int(np.sum((y_pred == c) & (y_true == c)))
        fp = int(np.sum((y_pred == c) & (y_true != c)))
        fn = int(np.sum((y_pred != c) & (y_true == c)))
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)

    return {
        "accuracy": accuracy,
        "precision_macro": float(np.mean(precisions)) if precisions else 0.0,
        "recall_macro":    float(np.mean(recalls))    if recalls    else 0.0,
        "f1_macro":        float(np.mean(f1s))        if f1s        else 0.0,
    }


def _assert_metrics_match(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    test_id: str,
    tol: float = 1e-9,
) -> None:
    prod = compute_metrics(y_true, y_pred)
    ref = _ref_metrics(y_true, y_pred)
    for key in ("accuracy", "precision_macro", "recall_macro", "f1_macro"):
        assert abs(prod[key] - ref[key]) < tol, (
            f"[{test_id}] Metric '{key}' mismatch:\n"
            f"  production: {prod[key]}\n"
            f"  reference : {ref[key]}\n"
            f"  diff      : {abs(prod[key] - ref[key])}"
        )


# ── DT-METR-01: Perfect binary predictions ────────────────────────────────────

def test_dt_metr01_perfect_binary():
    """DT-METR-01: All correct → accuracy=1.0, precision=1.0, recall=1.0, F1=1.0."""
    y_true = np.array([0, 0, 1, 1, 0, 1])
    y_pred = y_true.copy()
    _assert_metrics_match(y_true, y_pred, "DT-METR-01")
    prod = compute_metrics(y_true, y_pred)
    assert prod["accuracy"] == 1.0
    assert abs(prod["f1_macro"] - 1.0) < 1e-9


# ── DT-METR-02: All wrong binary predictions ──────────────────────────────────

def test_dt_metr02_all_wrong_binary():
    """DT-METR-02: All wrong (flipped) → known degenerate metric values."""
    y_true = np.array([0, 0, 1, 1])
    y_pred = np.array([1, 1, 0, 0])   # perfectly inverted
    _assert_metrics_match(y_true, y_pred, "DT-METR-02")
    prod = compute_metrics(y_true, y_pred)
    assert prod["accuracy"] == 0.0


# ── DT-METR-03: Mixed binary predictions ──────────────────────────────────────

@pytest.mark.parametrize("seed", [0, 42, 99, 123, 7])
def test_dt_metr03_mixed_binary(seed: int):
    """DT-METR-03: Random binary predictions: scalar metrics match reference."""
    rng = np.random.default_rng(seed)
    y_true = rng.integers(0, 2, size=200)
    y_pred = rng.integers(0, 2, size=200)
    _assert_metrics_match(y_true, y_pred, f"DT-METR-03 seed={seed}")


# ── DT-METR-04: 3-class multiclass ───────────────────────────────────────────

@pytest.mark.parametrize("seed", [0, 42, 99])
def test_dt_metr04_multiclass_3class(seed: int):
    """DT-METR-04: 3-class accuracy and macro-F1 match reference."""
    rng = np.random.default_rng(seed)
    y_true = rng.integers(0, 3, size=300)
    y_pred = rng.integers(0, 3, size=300)
    _assert_metrics_match(y_true, y_pred, f"DT-METR-04 seed={seed}")


# ── DT-METR-05: Imbalanced multiclass ────────────────────────────────────────

def test_dt_metr05_imbalanced():
    """DT-METR-05: Imbalanced dataset — macro-F1 reflects per-class performance."""
    rng = np.random.default_rng(7)
    # 90% class 0, 10% class 1 → macro metrics penalise ignoring minority
    y_true = np.concatenate([np.zeros(180, dtype=int), np.ones(20, dtype=int)])
    y_pred = np.zeros(200, dtype=int)  # trivial majority classifier
    _assert_metrics_match(y_true, y_pred, "DT-METR-05")
    prod = compute_metrics(y_true, y_pred)
    # Majority-only classifier has 0 recall for class 1 → macro recall < 0.6
    assert prod["recall_macro"] < 0.6, (
        f"[DT-METR-05] Macro recall should be < 0.6 for majority-only classifier, "
        f"got {prod['recall_macro']}"
    )


# ── DT-METR-06: FPR and FNR via confusion matrix ─────────────────────────────

def test_dt_metr06_fpr_fnr():
    """DT-METR-06: FPR and FNR match direct confusion-matrix arithmetic."""
    y_true = np.array([0, 0, 0, 1, 1, 1, 1, 0])
    y_pred = np.array([0, 1, 0, 1, 0, 1, 1, 1])  # some FP and FN

    prod = compute_metrics(y_true, y_pred)

    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))

    ref_fpr = fp / (fp + tn) if (fp + tn) > 0 else None
    ref_fnr = fn / (fn + tp) if (fn + tp) > 0 else None

    if ref_fpr is not None and prod.get("false_positive_rate") is not None:
        assert abs(prod["false_positive_rate"] - ref_fpr) < 1e-6, (
            f"[DT-METR-06] FPR mismatch: prod={prod['false_positive_rate']}, ref={ref_fpr}"
        )
    if ref_fnr is not None and prod.get("false_negative_rate") is not None:
        assert abs(prod["false_negative_rate"] - ref_fnr) < 1e-6, (
            f"[DT-METR-06] FNR mismatch: prod={prod['false_negative_rate']}, ref={ref_fnr}"
        )
    # Raw confusion matrix counts
    assert prod.get("true_positive") == tp
    assert prod.get("true_negative") == tn
    assert prod.get("false_positive") == fp
    assert prod.get("false_negative") == fn


# ── DT-METR-07: Determinism ───────────────────────────────────────────────────

def test_dt_metr07_determinism():
    """DT-METR-07: Same inputs always produce identical metrics."""
    y_true = np.array([0, 1, 0, 1, 1, 0, 0, 1])
    y_pred = np.array([0, 1, 1, 1, 0, 0, 1, 1])
    first = compute_metrics(y_true, y_pred)
    for _ in range(5):
        again = compute_metrics(y_true, y_pred)
        for key in ("accuracy", "precision_macro", "recall_macro", "f1_macro"):
            assert first[key] == again[key], (
                f"[DT-METR-07] Non-deterministic metric '{key}': {first[key]} vs {again[key]}"
            )


# ── DT-METR-08: Class distribution proportions sum to 1.0 ────────────────────

@pytest.mark.parametrize("n_classes,seed", [(2, 0), (3, 1), (5, 42)])
def test_dt_metr08_class_distribution(n_classes: int, seed: int):
    """DT-METR-08: class_distribution proportions sum to 1.0."""
    rng = np.random.default_rng(seed)
    y_true = rng.integers(0, n_classes, size=500)
    y_pred = rng.integers(0, n_classes, size=500)
    prod = compute_metrics(y_true, y_pred)
    dist = prod["class_distribution"]
    proportions_sum = sum(dist["proportions"].values())
    assert abs(proportions_sum - 1.0) < 1e-6, (
        f"[DT-METR-08] Class proportions do not sum to 1.0: {proportions_sum}"
    )
    counts_sum = sum(dist["counts"].values())
    assert counts_sum == len(y_true), (
        f"[DT-METR-08] Class counts do not sum to n_samples: {counts_sum} vs {len(y_true)}"
    )
