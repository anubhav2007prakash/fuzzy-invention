"""Model Evaluator harness for SentinelCrypt AI.

Evaluates trained detectors against held-out test splits, measuring both
predictive performance (accuracy, F1, AUC) and operational metrics (latency).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np

from backend.app.ml.evaluation.metrics import (
    compute_confusion_matrix_dict,
    compute_detailed_report,
    compute_metrics,
)
from backend.app.ml.models.base import BaseDetector


@dataclass
class EvaluationResult:
    """Encapsulates all evaluation artifacts from an evaluation run."""
    metrics: Dict[str, Any]
    confusion_matrix: Dict[str, Any]
    classification_report: Dict[str, Any]
    latency_ms_per_sample: float
    total_samples: int
    execution_time_s: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics": self.metrics,
            "confusion_matrix": self.confusion_matrix,
            "classification_report": self.classification_report,
            "latency_ms_per_sample": self.latency_ms_per_sample,
            "total_samples": self.total_samples,
            "execution_time_s": self.execution_time_s,
        }


class ModelEvaluator:
    """Evaluates BaseDetector instances on test datasets."""

    def __init__(self):
        pass

    def evaluate(
        self,
        model: BaseDetector,
        X_test: np.ndarray,
        y_test: np.ndarray,
        label_names: Optional[List[str]] = None,
    ) -> EvaluationResult:
        """Run evaluation pipeline on a model with test data.

        Args:
            model: Fitted BaseDetector instance.
            X_test: 2D numpy array of preprocessed test features.
            y_test: 1D numpy array of ground truth test labels.
            label_names: Optional string names for the classes.

        Returns:
            EvaluationResult dataclass.
        """
        n_samples = len(X_test)
        if n_samples == 0:
            raise ValueError("Cannot evaluate model on empty test dataset.")

        # Measure latency
        start_time = time.perf_counter()
        y_pred = model.predict(X_test)
        inference_time = time.perf_counter() - start_time
        latency_ms_per_sample = (inference_time / n_samples) * 1000.0

        # Probabilities
        y_prob = None
        try:
            y_prob = model.predict_proba(X_test)
        except Exception:
            pass

        # Compute metrics
        metrics = compute_metrics(
            y_true=y_test,
            y_pred=y_pred,
            y_prob=y_prob,
            label_names=label_names,
        )
        metrics["latency_ms_per_sample"] = float(round(latency_ms_per_sample, 4))

        cm = compute_confusion_matrix_dict(
            y_true=y_test,
            y_pred=y_pred,
            label_names=label_names,
        )

        detailed = compute_detailed_report(
            y_true=y_test,
            y_pred=y_pred,
            label_names=label_names,
        )

        return EvaluationResult(
            metrics=metrics,
            confusion_matrix=cm,
            classification_report=detailed,
            latency_ms_per_sample=float(round(latency_ms_per_sample, 4)),
            total_samples=n_samples,
            execution_time_s=float(round(inference_time, 4)),
        )
