"""Explanation Stability Analyzer.

Measures how stable SHAP feature attributions are under controlled Gaussian
perturbations of the transformed input features.

Methodology (EXP-B — see 22_Experiment_Design.md):
    1. Compute baseline SHAP explanation for X.
    2. Perturb continuous features with Gaussian noise (σ = `noise_std`).
    3. Recompute SHAP explanation for the perturbed sample.
    4. Measure cosine similarity between baseline and perturbed SHAP vectors.
    5. Repeat `n_repetitions` times.
    6. Return mean cosine similarity as `stability_score` ∈ [0, 1].

DISCLAIMER:
    Stability measures consistency of the *model's attribution*, not causal
    correctness.  A high stability score means the explanation is consistent
    under perturbation, not that the features cause the predicted outcome.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np

from backend.app.core.logging import get_logger
from backend.app.xai.shap_explainer import SHAPExplainer, SHAPResult

logger = get_logger(__name__)


@dataclass
class StabilityReport:
    """Output of an explanation stability analysis run."""

    stability_score: float        # mean cosine similarity over repetitions
    cosine_similarities: List[float] = field(default_factory=list)
    n_repetitions: int = 20
    noise_std: float = 0.05

    @property
    def std(self) -> float:
        """Standard deviation of per-repetition cosine similarities."""
        if len(self.cosine_similarities) < 2:
            return 0.0
        return float(np.std(self.cosine_similarities, ddof=1))


class ExplanationStabilityAnalyzer:
    """Computes explanation stability score for a fitted SHAPExplainer.

    Args:
        explainer: A ready-to-use SHAPExplainer.
        n_repetitions: Number of perturbed repetitions (default 20).
        noise_std: Standard deviation of additive Gaussian noise (default 0.05).
        random_seed: RNG seed for reproducibility (default 42).
    """

    def __init__(
        self,
        explainer: SHAPExplainer,
        n_repetitions: int = 20,
        noise_std: float = 0.05,
        random_seed: int = 42,
    ) -> None:
        self._explainer = explainer
        self._n_repetitions = n_repetitions
        self._noise_std = noise_std
        self._rng = np.random.RandomState(random_seed)  # noqa: NPY002

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_vector(result: SHAPResult) -> np.ndarray:
        """Convert SHAPResult contributions to a flat numpy vector."""
        return np.array([c.shap_value for c in result.contributions], dtype=np.float64)

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two 1-D vectors.

        Returns 1.0 if either vector is the zero vector (degenerate case).
        """
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 1.0  # zero vector → treat as identical (no signal)
        return float(np.clip(np.dot(a, b) / (norm_a * norm_b), -1.0, 1.0))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, X: np.ndarray) -> StabilityReport:
        """Compute stability score for a single transformed sample.

        Args:
            X: Transformed sample of shape (1, n_features).

        Returns:
            StabilityReport with stability_score and per-repetition details.
        """
        if X.shape[0] != 1:
            raise ValueError(
                f"ExplanationStabilityAnalyzer.analyze() expects exactly 1 sample; "
                f"got {X.shape[0]}"
            )

        # Baseline SHAP vector
        baseline_result = self._explainer.explain(X)
        baseline_vec = self._to_vector(baseline_result)

        cosine_sims: List[float] = []

        for _ in range(self._n_repetitions):
            noise = self._rng.normal(loc=0.0, scale=self._noise_std, size=X.shape)
            X_perturbed = X + noise

            try:
                perturbed_result = self._explainer.explain(X_perturbed)
                perturbed_vec = self._to_vector(perturbed_result)
                sim = self._cosine_similarity(baseline_vec, perturbed_vec)
            except Exception as exc:
                logger.warning("Stability repetition failed: %s; using sim=0.0", exc)
                sim = 0.0

            cosine_sims.append(sim)

        stability_score = float(np.mean(cosine_sims)) if cosine_sims else 0.0

        return StabilityReport(
            stability_score=stability_score,
            cosine_similarities=cosine_sims,
            n_repetitions=self._n_repetitions,
            noise_std=self._noise_std,
        )
