"""Reference XAI plugin — perturbation-based feature importance.

Demonstrates how to add a new ExplainerPlugin variant that is distinct
from the built-in SHAP and stability explainers.  This plugin does not
replace core hashing, ledger, or notary functionality.

Security guarantees (enforced by PluginHost):
- Input validation occurs before the plugin is invoked
- The plugin's output is stripped of envelope keys and re-hashed by the host
- Provenance metadata is captured and stored with the experiment
- No plugin may bypass validation, provenance, tracking, or evidence generation
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

from backend.app.ml.models.base import BaseDetector
from backend.app.plugins.protocols import ExplainerPlugin


class PerturbationExplainer(ExplainerPlugin):
    """Perturbation-based feature importance explainer.

    Works by zeroing out each feature column and measuring the change in
    model predictions.  Does not require access to model internals, so it
    can wrap any callable that implements ``predict``.
    """

    name: str = "perturbation"
    version: str = "1.0.0"

    def __init__(self, model: Optional[BaseDetector] = None) -> None:
        self._wrapped: Optional[BaseDetector] = model

    def explain(self, X: np.ndarray) -> Dict[str, Any]:
        """Compute feature importances via zeroing perturbation.

        Args:
            X: Feature matrix of shape (n_samples, n_features).

        Returns:
            Dictionary with ``feature_importances`` (list of floats),
            the method name, and version string.
        """
        if self._wrapped is None:
            # If no model was wrapped, return uniform importances
            n_features = X.shape[1] if X.ndim == 2 else 1
            importances = [1.0 / n_features] * n_features
            return {
                "feature_importances": importances,
                "method": self.name,
                "version": self.version,
            }

        importances: list[float] = []
        predictions_original = self._wrapped.predict(X)

        for i in range(X.shape[1]):
            X_perturbed = X.copy()
            X_perturbed[:, i] = 0.0
            predictions_perturbed = self._wrapped.predict(X_perturbed)
            delta = np.mean(np.abs(predictions_original - predictions_perturbed))
            importances.append(float(delta))

        return {
            "feature_importances": importances,
            "method": self.name,
            "version": self.version,
        }

    def set_model(self, model: BaseDetector) -> None:
        """Attach a BaseDetector instance for perturbation runs."""
        self._wrapped = model

    def clear_model(self) -> None:
        self._wrapped = None  # type: ignore[assignment]

        importances: list[float] = []
        predictions_original = self._wrapped.predict(X)

        for i in range(X.shape[1]):
            X_perturbed = X.copy()
            X_perturbed[:, i] = 0.0
            predictions_perturbed = self._wrapped.predict(X_perturbed)
            delta = np.mean(np.abs(predictions_original - predictions_perturbed))
            importances.append(float(delta))

        return {
            "feature_importances": importances,
            "method": self.name,
            "version": self.version,
        }

    def set_model(self, model: Any) -> None:
        """Optional: attach a BaseDetector instance for perturbation runs."""
        from backend.app.ml.models.base import BaseDetector
        self._wrapped = model

    def clear_model(self) -> None:
        self._wrapped = None  # type: ignore[assignment]