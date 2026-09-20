"""Performance Metrics Engine for SentinelCrypt AI.

Calculates comprehensive classification, probabilistic, and error metrics:
- Accuracy, Precision, Recall, Specificity, F1 (Macro & Weighted)
- ROC-AUC & PR-AUC (with robust fallbacks for edge-case class distributions)
- Brier Score (Probability Calibration)
- Confusion Matrix & Per-Class Performance
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
