"""Logistic Regression Intrusion Detector for SentinelCrypt AI.

Linear baseline detector with L2 regularization, providing direct feature
coefficient interpretability, fast convergence, and calibrated probabilities.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

from backend.app.core.exceptions import ModelTrainingError
from backend.app.ml.models.base import BaseDetector


class LogisticRegressionDetector(BaseDetector):
    """Logistic Regression baseline classifier."""

    def __init__(
        self,
        hyperparameters: Optional[Dict[str, Any]] = None,
        random_seed: int = 42,
    ):
        super().__init__(
            model_type="logistic_regression",
            hyperparameters=hyperparameters or {},
            random_seed=random_seed,
        )
        # Set default parameters and override with user hyperparameters
        params = {
            "C": 1.0,
            "max_iter": 1000,
            "solver": "lbfgs",
            "random_state": random_seed,
        }
        params.update(self.hyperparameters)
        self.hyperparameters = params
        self._model = LogisticRegression(**self.hyperparameters)

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> "LogisticRegressionDetector":
        """Fit logistic regression model on scaled feature array."""
        try:
            self._model.fit(X, y)
            self.classes_ = np.array(self._model.classes_)
            self.feature_names = feature_names
            self.is_fitted = True
            return self
        except Exception as e:
            raise ModelTrainingError(f"Logistic Regression training failed: {str(e)}") from e

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict binary/multiclass labels."""
        if not self.is_fitted:
            raise ModelTrainingError("Model must be fitted before calling predict.")
        return self._model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict posterior probabilities."""
        if not self.is_fitted:
            raise ModelTrainingError("Model must be fitted before calling predict_proba.")
        return self._model.predict_proba(X)

    @property
    def coefficients(self) -> np.ndarray:
        """Return model coefficients."""
        if not self.is_fitted:
            raise ModelTrainingError("Model must be fitted to access coefficients.")
        return self._model.coef_

    @property
    def intercept(self) -> np.ndarray:
        """Return model intercept."""
        if not self.is_fitted:
            raise ModelTrainingError("Model must be fitted to access intercept.")
        return self._model.intercept_

    def get_feature_coefficients(self) -> Dict[str, float]:
        """Return dictionary mapping feature names to their learned weights (for binary class)."""
        if not self.is_fitted:
            raise ModelTrainingError("Model must be fitted to inspect feature weights.")
        if self.feature_names is None:
            return {}
        coefs = self._model.coef_[0] if len(self._model.coef_) == 1 else self._model.coef_[0]
        return {name: float(w) for name, w in zip(self.feature_names, coefs)}

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
        }
        joblib.dump(payload, target)

    @classmethod
    def load(cls, path: Union[str, Path]) -> "LogisticRegressionDetector":
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
        return instance
