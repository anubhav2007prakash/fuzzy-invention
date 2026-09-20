"""SHAP Explainer Implementation.

Provides SHAPExplainer which wraps shap.LinearExplainer (LogisticRegression)
and shap.TreeExplainer (RandomForest) to produce per-feature attributions.

IMPORTANT DISCLAIMER:
    SHAP values describe how a *trained model* distributes its prediction
    across input features for a specific sample.  They are **not** causal
    ground-truth explanations and must not be interpreted as such.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import shap

from backend.app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FeatureContribution:
    """Single-feature SHAP attribution."""

    feature: str
    value: Any          # raw (unscaled) feature value
    shap_value: float   # SHAP attribution score
    importance: float   # |shap_value| — for ranking


@dataclass
class SHAPResult:
    """Output of a single-sample SHAP explanation run."""

    method: str
    base_value: float
    contributions: List[FeatureContribution] = field(default_factory=list)

    def top_k(self, k: int) -> List[FeatureContribution]:
        """Return top-k features by absolute SHAP value (descending)."""
        return sorted(self.contributions, key=lambda c: c.importance, reverse=True)[:k]

    def top_k_as_json(self, k: int) -> str:
        """Return JSON string of top-k feature contributions."""
        items = [
            {
                "feature": c.feature,
                "value": c.value,
                "shap_value": c.shap_value,
                "importance": c.importance,
            }
            for c in self.top_k(k)
        ]
        return json.dumps(items)


class SHAPExplainer:
    """Thin wrapper around SHAP library for SentinelCrypt AI.

    Supports:
    - LogisticRegressionDetector  → shap.LinearExplainer
    - RandomForestDetector        → shap.TreeExplainer

    Usage::

        explainer = SHAPExplainer(detector, X_background, feature_names)
        result = explainer.explain(X_single_row)
        top5 = result.top_k(5)
    """

    _LINEAR_TYPE = "logistic_regression"
    _TREE_TYPE = "random_forest"

    def __init__(
        self,
        detector: Any,
        X_background: np.ndarray,
        feature_names: List[str],
    ) -> None:
        """Initialise and pre-build the SHAP explainer.

        Args:
            detector: A fitted BaseDetector (LogisticRegressionDetector or
                      RandomForestDetector) — raw_model must return sklearn estimator.
            X_background: Representative background data (n_samples, n_features).
                          Used only by LinearExplainer.
            feature_names: Ordered list of feature column names.
        """
        self._detector = detector
        self._feature_names = feature_names
        self._model_type = getattr(detector, "model_type", "").lower()
        self._raw_model = detector.raw_model
        self._explainer = self._build_explainer(X_background)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_explainer(self, X_background: np.ndarray) -> Any:
        if self._model_type == self._LINEAR_TYPE:
            logger.debug("Building LinearExplainer for LogisticRegression")
            masker = shap.maskers.Independent(X_background)
            return shap.LinearExplainer(self._raw_model, masker)
        elif self._model_type == self._TREE_TYPE:
            logger.debug("Building TreeExplainer for RandomForest")
            return shap.TreeExplainer(self._raw_model)
        else:
            # Fallback: try LinearExplainer with Independent masker
            logger.warning(
                "Unknown model type '%s'; falling back to LinearExplainer", self._model_type
            )
            masker = shap.maskers.Independent(X_background)
            return shap.LinearExplainer(self._raw_model, masker)

    def _extract_shap_values(
        self, shap_explanation: Any
    ) -> np.ndarray:
        """Extract a 1-D SHAP array of shape (n_features,) for the positive class.

        - LinearExplainer returns shape (1, n_features) — take row 0.
        - TreeExplainer for binary classification returns (1, n_features, 2)
          or (1, n_features); take column 1 (positive class) if 3-D.
        """
        vals: np.ndarray = np.array(shap_explanation.values)

        if vals.ndim == 3:
            # (1, n_features, n_classes) — pick class-1 slice
            vals = vals[0, :, 1]
        elif vals.ndim == 2:
            # (1, n_features)
            vals = vals[0]
        else:
            vals = vals.flatten()

        return vals

    def _extract_base_value(self, shap_explanation: Any) -> float:
        """Extract scalar base value for the positive class."""
        base = np.array(shap_explanation.base_values)
        if base.ndim == 2:
            # (1, n_classes) — pick class-1
            return float(base[0, 1])
        elif base.ndim == 1:
            return float(base[0])
        return float(base)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def explain(
        self,
        X: np.ndarray,
        raw_sample: Optional[Dict[str, Any]] = None,
    ) -> SHAPResult:
        """Compute SHAP explanation for a single transformed sample.

        Args:
            X: Transformed single-row array of shape (1, n_features).
            raw_sample: Optional dict of {feature: original_value} for display.

        Returns:
            SHAPResult with per-feature contributions.
        """
        if X.shape[0] != 1:
            raise ValueError(
                f"SHAPExplainer.explain() expects exactly 1 sample; got {X.shape[0]}"
            )

        shap_exp = self._explainer(X)
        shap_vals = self._extract_shap_values(shap_exp)
        base_val = self._extract_base_value(shap_exp)

        contributions: List[FeatureContribution] = []
        for i, fname in enumerate(self._feature_names):
            sv = float(shap_vals[i]) if i < len(shap_vals) else 0.0
            raw_val: Any = float(X[0, i]) if i < X.shape[1] else None
            if raw_sample is not None:
                raw_val = raw_sample.get(fname, raw_val)
            contributions.append(
                FeatureContribution(
                    feature=fname,
                    value=raw_val,
                    shap_value=sv,
                    importance=abs(sv),
                )
            )

        return SHAPResult(
            method="SHAP-Linear" if self._model_type == self._LINEAR_TYPE else "SHAP-Tree",
            base_value=base_val,
            contributions=contributions,
        )
