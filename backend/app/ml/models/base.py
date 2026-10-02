"""Base Model Interface for SentinelCrypt AI intrusion detection engines.

All detection models (LogisticRegression, RandomForest, etc.) must implement
BaseDetector to ensure uniform training, inference, serialization, and XAI
interoperability.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

from backend.app.ml.calibration import ProbabilityCalibrator


class BaseDetector(ABC):
    """Abstract base detector interface."""

    def __init__(
        self,
        model_type: str,
        hyperparameters: Optional[Dict[str, Any]] = None,
        random_seed: int = 42,
    ):
        self.model_type = model_type
        self.hyperparameters = hyperparameters or {}
        self.random_seed = random_seed
        self.is_fitted: bool = False
        self.classes_: Optional[np.ndarray] = None
        self.feature_names: Optional[List[str]] = None
        self.calibrator: Optional[ProbabilityCalibrator] = None

    @property
    def calibration_configuration(self) -> Dict[str, Any]:
        """Calibration metadata persisted with this model, if configured."""
        if self.calibrator is None:
            return {"enabled": False, "method": "none"}
        return {"enabled": True, **self.calibrator.configuration}

    def set_calibrator(self, calibrator: ProbabilityCalibrator) -> None:
        """Attach a post-hoc calibrator fitted on a reserved calibration split."""
        if self.classes_ is None or not np.array_equal(self.classes_, calibrator.classes):
            raise ValueError("Calibrator classes must match the fitted detector classes.")
        self.calibrator = calibrator

    def apply_calibration(self, probabilities: np.ndarray) -> np.ndarray:
        """Apply fitted post-hoc calibration while retaining raw estimator support."""
        if self.calibrator is None:
            return probabilities
        return self.calibrator.predict_proba(probabilities)

    @abstractmethod
    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> "BaseDetector":
        """Fit the detector on training data.

        Args:
            X: 2D numpy array of shape (n_samples, n_features).
            y: 1D numpy array of target class integers.
            feature_names: Optional list of feature column names.
        """
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class labels for samples in X.

        Args:
            X: 2D numpy array of shape (n_samples, n_features).

        Returns:
            1D numpy array of predicted class integers.
        """
        pass

    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities for samples in X.

        Args:
            X: 2D numpy array of shape (n_samples, n_features).

        Returns:
            2D numpy array of shape (n_samples, n_classes).
        """
        pass

    @abstractmethod
    def save(self, path: Union[str, Path]) -> None:
        """Persist model state and metadata to disk.

        Args:
            path: Destination file path.
        """
        pass

    @classmethod
    @abstractmethod
    def load(cls, path: Union[str, Path]) -> "BaseDetector":
        """Load a persisted detector from disk.

        Args:
            path: Source file path.

        Returns:
            Loaded BaseDetector instance.
        """
        pass

    @property
    def raw_model(self) -> Any:
        """Return the underlying scikit-learn or ML framework estimator."""
        return getattr(self, "_model", None)
