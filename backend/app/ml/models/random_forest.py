"""Random Forest Intrusion Detector for SentinelCrypt AI.

Non-linear ensemble classifier composed of decision trees, designed to capture
complex feature interactions and non-linear boundaries in network flow data.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from backend.app.core.exceptions import ModelTrainingError
from backend.app.ml.models.base import BaseDetector


class RandomForestDetector(BaseDetector):
    """Random Forest ensemble classifier."""

    def __init__(
        self,
        hyperparameters: Optional[Dict[str, Any]] = None,
        random_seed: int = 42,
    ):
        super().__init__(
            model_type="random_forest",
            hyperparameters=hyperparameters or {},
            random_seed=random_seed,
        )
        # Default hyperparameters based on specification
        params = {
            "n_estimators": 100,
            "max_depth": 15,
            "random_state": random_seed,
            "n_jobs": -1,
        }
        params.update(self.hyperparameters)
        self.hyperparameters = params
        self._model = RandomForestClassifier(**self.hyperparameters)

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> "RandomForestDetector":
        """Fit the random forest on feature matrix."""
        try:
            self._model.fit(X, y)
            self.classes_ = np.array(self._model.classes_)
            self.feature_names = feature_names
            self.is_fitted = True
            return self
        except Exception as e:
            raise ModelTrainingError(f"Random Forest training failed: {str(e)}") from e

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class labels."""
        if not self.is_fitted:
            raise ModelTrainingError("Model must be fitted before calling predict.")
        return self._model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities."""
        if not self.is_fitted:
            raise ModelTrainingError("Model must be fitted before calling predict_proba.")
        return self.apply_calibration(self._model.predict_proba(X))

    @property
    def feature_importances_(self) -> np.ndarray:
        """Return Gini impurity-based feature importances."""
        if not self.is_fitted:
            raise ModelTrainingError("Model must be fitted to access feature importances.")
        return self._model.feature_importances_

    def get_feature_importances(self) -> Dict[str, float]:
        """Return dictionary mapping feature name to importance score."""
        if not self.is_fitted:
            raise ModelTrainingError("Model must be fitted to inspect feature importances.")
        if self.feature_names is None:
            return {}
        importances = self._model.feature_importances_
        return {name: float(imp) for name, imp in zip(self.feature_names, importances)}

    def save(self, path: Union[str, Path]) -> None:
        """Persist detector state to disk."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model_type": self.model_type,
            "hyperparameters": self.hyperparameters,
            "random_seed": self.random_seed,
            "is_fitted": self.is_fitted,
            "classes_": self.classes_,
            "feature_names": self.feature_names,
            "raw_model": self._model,
            "calibrator": self.calibrator,
        }
        joblib.dump(payload, target)

    @classmethod
    def load(cls, path: Union[str, Path]) -> "RandomForestDetector":
        """Load persisted detector from disk."""
        target = Path(path)
        if not target.exists():
            raise FileNotFoundError(f"Model file not found at: {target}")
        payload = joblib.load(target)
        instance = cls(
            hyperparameters=payload.get("hyperparameters", {}),
            random_seed=payload.get("random_seed", 42),
        )
        instance.is_fitted = payload.get("is_fitted", False)
        instance.classes_ = payload.get("classes_")
        instance.feature_names = payload.get("feature_names")
        instance._model = payload.get("raw_model")
        instance.calibrator = payload.get("calibrator")
        return instance
