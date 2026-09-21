"""Performance Metrics Engine for SentinelCrypt AI.

EVALUATION STRATEGY
--------------------
Network intrusion detection datasets are typically imbalanced: benign traffic
outweighs attacks, sometimes by 10:1 or more.  In this context accuracy alone
is misleading — a model that always predicts "benign" can achieve 90%+ accuracy
while detecting zero attacks.  We therefore use a multi-metric strategy:

Primary metrics (always reported):
  - f1_macro: Harmonic mean of precision and recall, averaged equally across
    classes.  Unlike accuracy, it does not reward ignoring the minority class.
  - precision_macro: Of all positive predictions, how many are correct?
    High precision = few false alarms.
  - recall_macro: Of all actual positives, how many were detected?
    High recall = few missed attacks.

Supplementary metrics (reported when probabilities are available):
  - pr_auc (Precision-Recall AUC): More informative than ROC-AUC under
    class imbalance because it focuses on the minority (attack) class.
  - roc_auc: Area under the ROC curve; threshold-independent but can be
    optimistic when the negative class dominates.
  - brier_score: Measures probability calibration (lower = better).

Operational metrics:
  - false_positive_rate: Critical for IDS — high FPR causes alert fatigue.
  - false_negative_rate: Critical for IDS — high FNR means missed attacks.
  - class_distribution: Reports the actual class proportions so the analyst
    can interpret metrics in context.

Class imbalance approach:
  The current pipeline uses stratified train/test splitting (preserving class
  ratios) and does NOT apply SMOTE, class weighting, or resampling.  This
  is a deliberate baseline: we want to measure how well the model learns from
  the natural distribution, without augmentation that could mask generalization
  problems.  Future work may add class_weight='balanced' or SMOTE as a
  controlled experiment variable.

Per-class metrics:
  compute_detailed_report() returns sklearn's classification_report as a dict,
  giving precision, recall, f1, and support for each class.  This is essential
  because aggregate metrics can hide poor performance on specific attack types.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from backend.app.core.logging import get_logger

logger = get_logger(__name__)


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray] = None,
    label_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Compute standard detection and classification performance metrics.

    Args:
        y_true: Ground truth target labels (1D array).
        y_pred: Model predicted labels (1D array).
        y_prob: Predicted probabilities (2D array, shape n_samples x n_classes).
        label_names: Optional list of string names for classes.

    Returns:
        Dictionary of computed metric values.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    classes = np.unique(y_true)
    n_classes = len(classes)

    metrics: Dict[str, Any] = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "precision_weighted": float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
        "recall_macro": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_weighted": float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        "roc_auc": None,
        "pr_auc": None,
        "brier_score": None,
    }

    # Standard shorthand aliases for convenience
    metrics["precision"] = metrics["precision_macro"]
    metrics["recall"] = metrics["recall_macro"]
    metrics["f1"] = metrics["f1_macro"]

    # Class distribution (for imbalance analysis)
    class_counts = {str(c): int(np.sum(y_true == c)) for c in classes}
    total = len(y_true)
    metrics["class_distribution"] = {
        "counts": class_counts,
        "proportions": {k: round(v / total, 4) for k, v in class_counts.items()},
        "n_classes": int(n_classes),
        "is_imbalanced": bool(n_classes == 2 and min(class_counts.values()) / total < 0.1),
    }

    # False Positive Rate (for binary classification)
    if n_classes == 2:
        tn = int(np.sum((y_true == 0) & (y_pred == 0)))
        fp = int(np.sum((y_true == 0) & (y_pred == 1)))
        fn = int(np.sum((y_true == 1) & (y_pred == 0)))
        tp = int(np.sum((y_true == 1) & (y_pred == 1)))
        metrics["false_positive_rate"] = round(fp / (fp + tn), 6) if (fp + tn) > 0 else None
        metrics["false_negative_rate"] = round(fn / (fn + tp), 6) if (fn + tp) > 0 else None
        metrics["true_positive"] = tp
        metrics["true_negative"] = tn
        metrics["false_positive"] = fp
        metrics["false_negative"] = fn

    # Compute probabilistic metrics if probabilities are provided
    if y_prob is not None:
        y_prob = np.asarray(y_prob)
        if n_classes == 2:
            # Binary classification
            prob_col = y_prob[:, 1] if y_prob.ndim > 1 and y_prob.shape[1] > 1 else y_prob.ravel()
            try:
                metrics["roc_auc"] = float(roc_auc_score(y_true, prob_col))
            except Exception as e:
                logger.warning("ROC-AUC computation failed: %s", e)
                metrics["roc_auc"] = None

            try:
                metrics["pr_auc"] = float(average_precision_score(y_true, prob_col))
            except Exception as e:
                logger.warning("PR-AUC computation failed: %s", e)
                metrics["pr_auc"] = None

            try:
                metrics["brier_score"] = float(brier_score_loss(y_true, prob_col))
            except Exception as e:
                logger.warning("Brier score computation failed: %s", e)
                metrics["brier_score"] = None

        elif n_classes > 2 and y_prob.ndim > 1:
            # Multi-class OvR
            try:
                metrics["roc_auc"] = float(
                    roc_auc_score(y_true, y_prob, multi_class="ovr", average="macro")
                )
            except Exception as e:
                logger.warning("Multi-class ROC-AUC computation failed: %s", e)
                metrics["roc_auc"] = None

    return metrics


def compute_confusion_matrix_dict(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    label_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Compute confusion matrix and return JSON-serializable structure."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    all_classes = np.unique(np.concatenate([y_true, y_pred]))

    cm = confusion_matrix(y_true, y_pred, labels=all_classes)

    labels = (
        [label_names[int(c)] if int(c) < len(label_names) else str(c) for c in all_classes]
        if label_names
        else [str(c) for c in all_classes]
    )

    return {
        "matrix": cm.tolist(),
        "labels": labels,
    }


def compute_detailed_report(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    label_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generate per-class precision, recall, f1, and support report."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    unique_classes = np.unique(np.concatenate([y_true, y_pred]))

    target_names = None
    if label_names:
        target_names = [
            label_names[int(c)] if int(c) < len(label_names) else str(c) for c in unique_classes
        ]

    return classification_report(
        y_true,
        y_pred,
        labels=unique_classes,
        target_names=target_names,
        output_dict=True,
        zero_division=0,
    )
