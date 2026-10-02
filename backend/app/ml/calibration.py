"""Probability calibration utilities for binary classifiers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

SUPPORTED_CALIBRATION_METHODS = {"sigmoid", "isotonic"}
ISOTONIC_MINIMUM_SAMPLES = 1000
SIGMOID_MINIMUM_SAMPLES = 50
MINIMUM_SAMPLES_PER_CLASS = 10


def _validated_binary_inputs(
    y_true: Sequence[int],
    positive_probability: Sequence[float],
) -> tuple[np.ndarray, np.ndarray]:
    labels = np.asarray(y_true)
    probabilities = np.asarray(positive_probability, dtype=float)
    if labels.ndim != 1 or probabilities.ndim != 1 or len(labels) != len(probabilities):
        raise ValueError("y_true and positive_probability must be equal-length vectors.")
    if not len(labels):
        raise ValueError("Calibration evaluation requires at least one sample.")
    if not np.isfinite(probabilities).all() or np.any(
        (probabilities < 0) | (probabilities > 1)
    ):
        raise ValueError("Probabilities must be finite values in [0, 1].")
    if not set(np.unique(labels)).issubset({0, 1}):
        raise ValueError("Calibration currently supports binary labels encoded as 0/1.")
    return labels.astype(int), probabilities


def reliability_diagram(
    y_true: Sequence[int],
    positive_probability: Sequence[float],
    n_bins: int = 10,
) -> Dict[str, Any]:
    """Return uniform-width bins of predicted positive probability vs frequency."""
    labels, probabilities = _validated_binary_inputs(y_true, positive_probability)
    if isinstance(n_bins, bool) or not isinstance(n_bins, int) or n_bins < 1:
        raise ValueError("n_bins must be a positive integer.")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins = []
    for index in range(n_bins):
        lower, upper = float(edges[index]), float(edges[index + 1])
        if index == 0:
            in_bin = (probabilities >= lower) & (probabilities <= upper)
        else:
            in_bin = (probabilities > lower) & (probabilities <= upper)
        count = int(in_bin.sum())
        bins.append({
            "lower": lower,
            "upper": upper,
            "mean_predicted_probability": (
                float(probabilities[in_bin].mean()) if count else None
            ),
            "observed_positive_frequency": (
                float(labels[in_bin].mean()) if count else None
            ),
            "sample_count": count,
        })
    return {
        "type": "uniform_width_binary_positive_probability",
        "n_bins": n_bins,
        "sample_count": len(labels),
        "bins": bins,
    }


def calibration_report(
    y_true: Sequence[int],
    positive_probability: Sequence[float],
    n_bins: int = 10,
) -> Dict[str, Any]:
    """Measure binary probability calibration without interpreting scores as certainty."""
    labels, probabilities = _validated_binary_inputs(y_true, positive_probability)
    diagram = reliability_diagram(labels, probabilities, n_bins=n_bins)
    ece = sum(
        bin_data["sample_count"] / len(labels)
        * abs(
            bin_data["observed_positive_frequency"]
            - bin_data["mean_predicted_probability"]
        )
        for bin_data in diagram["bins"]
        if bin_data["sample_count"]
    )
    return {
        "sample_count": len(labels),
        "brier_score": float(brier_score_loss(labels, probabilities)),
        "expected_calibration_error": float(ece),
        "ece_definition": (
            "Sample-weighted absolute difference between mean predicted positive "
            "probability and observed positive frequency in uniform-width bins."
        ),
        "reliability_diagram": diagram,
    }


@dataclass
class ProbabilityCalibrator:
    """Binary post-hoc calibration mapping fitted on a reserved calibration set."""

    method: str
    estimator: Any
    classes: np.ndarray
    positive_class_index: int
    configuration: Dict[str, Any]

    def predict_proba(self, probabilities: np.ndarray) -> np.ndarray:
        values = np.asarray(probabilities, dtype=float)
        if values.ndim != 2 or values.shape[1] != 2:
            raise ValueError("Probability calibrator requires an n-by-2 matrix.")
        positive_probability = values[:, self.positive_class_index]
        if self.method == "sigmoid":
            clipped = np.clip(positive_probability, 1e-6, 1.0 - 1e-6)
            score = np.log(clipped / (1.0 - clipped)).reshape(-1, 1)
            calibrated_positive = self.estimator.predict_proba(score)[:, 1]
        elif self.method == "isotonic":
            calibrated_positive = self.estimator.predict(positive_probability)
        else:
            raise ValueError(f"Unsupported calibration method '{self.method}'.")
        calibrated_positive = np.clip(calibrated_positive, 0.0, 1.0)
        calibrated = np.empty_like(values, dtype=float)
        calibrated[:, self.positive_class_index] = calibrated_positive
        calibrated[:, 1 - self.positive_class_index] = 1.0 - calibrated_positive
        return calibrated


def fit_probability_calibrator(
    method: str,
    y_calibration: Sequence[int],
    calibration_probabilities: np.ndarray,
    classes: Sequence[int],
) -> ProbabilityCalibrator:
    """Fit sigmoid or isotonic mapping on separate labelled calibration data.

    Isotonic regression is intentionally limited to at least 1,000 calibration
    observations to reduce overfitting risk; sigmoid calibration has a separate
    lower-bound and class-support requirement.
    """
    if not isinstance(method, str) or method not in SUPPORTED_CALIBRATION_METHODS:
        raise ValueError(
            "method must be 'sigmoid' or 'isotonic'; raw probabilities are not "
            "a calibration method."
        )
    labels = np.asarray(y_calibration)
    probabilities = np.asarray(calibration_probabilities, dtype=float)
    class_values = np.asarray(classes)
    if len(class_values) != 2 or set(class_values.tolist()) != {0, 1}:
        raise ValueError("Calibration currently supports only binary labels encoded as 0/1.")
    if labels.ndim != 1 or not len(labels) or not set(np.unique(labels)).issubset({0, 1}):
        raise ValueError("Calibration labels must be a non-empty binary 0/1 vector.")
    if probabilities.shape != (len(labels), 2):
        raise ValueError("Calibration probabilities must have shape (n_samples, 2).")
    if not len(labels) or not np.isfinite(probabilities).all():
        raise ValueError("Calibration data must be non-empty and finite.")
    if np.any((probabilities < 0) | (probabilities > 1)):
        raise ValueError("Calibration probabilities must be within [0, 1].")
    if not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-6):
        raise ValueError("Each calibration probability row must sum to 1.")
    counts = np.bincount(labels.astype(int), minlength=2)
    if len(labels) < SIGMOID_MINIMUM_SAMPLES or counts.min() < MINIMUM_SAMPLES_PER_CLASS:
        raise ValueError(
            "Calibration requires at least 50 rows and at least 10 rows per class."
        )
    if method == "isotonic" and len(labels) < ISOTONIC_MINIMUM_SAMPLES:
        raise ValueError(
            f"Isotonic calibration requires at least {ISOTONIC_MINIMUM_SAMPLES} "
            "reserved calibration rows."
        )
    positive_class_index = int(np.flatnonzero(class_values == 1)[0])
    positive_probability = probabilities[:, positive_class_index]
    if method == "sigmoid":
        clipped = np.clip(positive_probability, 1e-6, 1.0 - 1e-6)
        score = np.log(clipped / (1.0 - clipped)).reshape(-1, 1)
        estimator = LogisticRegression(solver="lbfgs", random_state=0)
        estimator.fit(score, labels.astype(int))
    else:
        estimator = IsotonicRegression(out_of_bounds="clip")
        estimator.fit(positive_probability, labels.astype(int))
    configuration = {
        "method": method,
        "fit_sample_count": int(len(labels)),
        "class_counts": {"0": int(counts[0]), "1": int(counts[1])},
        "positive_class": 1,
        "input": "base estimator's predicted positive-class probability",
        "fitted_on_reserved_calibration_partition": True,
    }
    return ProbabilityCalibrator(
        method=method,
        estimator=estimator,
        classes=class_values,
        positive_class_index=positive_class_index,
        configuration=configuration,
    )
