"""Offline, synthetic calibration study using disjoint fit/calibration/test data."""
from __future__ import annotations

import time
from typing import Any, Dict

import numpy as np
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from backend.app.ml.calibration import (
    calibration_report,
    fit_probability_calibrator,
)


def run_calibration_study(
    n_samples: int = 1200,
    method: str = "sigmoid",
    seed: int = 42,
) -> Dict[str, Any]:
    """Compare raw and post-hoc calibrated probabilities on the same held-out rows."""
    if isinstance(n_samples, bool) or not isinstance(n_samples, int) or n_samples < 400:
        raise ValueError("n_samples must be an integer of at least 400.")
    if not isinstance(method, str) or method not in {"sigmoid", "isotonic"}:
        raise ValueError("method must be 'sigmoid' or 'isotonic'.")

    X, y = make_classification(
        n_samples=n_samples,
        n_features=12,
        n_informative=8,
        n_redundant=2,
        n_repeated=0,
        n_classes=2,
        weights=[0.65, 0.35],
        flip_y=0.03,
        class_sep=0.9,
        random_state=seed,
    )
    X_fit_and_cal, X_test, y_fit_and_cal, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )
    X_fit, X_calibration, y_fit, y_calibration = train_test_split(
        X_fit_and_cal,
        y_fit_and_cal,
        test_size=0.2,
        random_state=seed + 1,
        stratify=y_fit_and_cal,
    )

    scaler = StandardScaler().fit(X_fit)
    X_fit_scaled = scaler.transform(X_fit)
    X_calibration_scaled = scaler.transform(X_calibration)
    X_test_scaled = scaler.transform(X_test)

    model = LogisticRegression(max_iter=1000, random_state=seed)
    model.fit(X_fit_scaled, y_fit)
    calibration_probabilities = model.predict_proba(X_calibration_scaled)
    raw_test_probabilities = model.predict_proba(X_test_scaled)
    calibrator = fit_probability_calibrator(
        method=method,
        y_calibration=y_calibration,
        calibration_probabilities=calibration_probabilities,
        classes=model.classes_,
    )
    calibrated_test_probabilities = calibrator.predict_proba(raw_test_probabilities)
    before = calibration_report(y_test, raw_test_probabilities[:, 1])
    after = calibration_report(y_test, calibrated_test_probabilities[:, 1])

    return {
        "experiment_id": "EXP-CALIBRATION",
        "title": "Prediction Probability Calibration Laboratory",
        "status": "COMPLETED",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "parameters": {
            "method": method,
            "n_samples": n_samples,
            "random_state": seed,
            "model_type": "logistic_regression",
            "data_source": "controlled synthetic classification fixture",
            "partition_counts": {
                "model_fit": int(len(y_fit)),
                "calibration": int(len(y_calibration)),
                "held_out_test": int(len(y_test)),
            },
        },
        "metrics": {
            "before": before,
            "after": after,
            "calibration_configuration": {
                **calibrator.configuration,
                "evaluation_partition": "held_out_test",
                "evaluation_sample_count": int(len(y_test)),
                "comparison_uses_same_test_observations": True,
            },
        },
        "interpretation": (
            "This synthetic, held-out comparison measures probability calibration "
            "on this fixture only. Raw model probabilities are not automatically "
            "equivalent to real-world confidence, and the result does not establish "
            "calibration under deployment distribution shift."
        ),
        "limitations": [
            "The data are generated synthetic observations, not operational traffic.",
            "The calibration mapping is fitted only on the reserved calibration partition.",
            "Both measurements use the same untouched held-out test partition.",
            "Calibration evidence is distribution-specific and may degrade under drift.",
        ],
    }
