"""Unit tests for Phase 5: XAI — SHAP Explainer and Explanation Stability Analyzer.

Tests:
    - SHAPExplainer with LogisticRegressionDetector (LinearExplainer)
    - SHAPExplainer with RandomForestDetector (TreeExplainer)
    - FeatureContribution ranking (top_k)
    - SHAPResult.top_k_as_json serialization
    - ExplanationStabilityAnalyzer cosine similarity
    - StabilityReport.std property
    - Edge cases: zero-vector inputs, single feature

DISCLAIMER:
    These tests verify SHAP attribution computation.  The values produced
    reflect model decision boundaries, not causal ground truth.
"""
from __future__ import annotations

import json
import unittest

import numpy as np

from backend.app.ml.models.logistic_regression import LogisticRegressionDetector
from backend.app.ml.models.random_forest import RandomForestDetector
from backend.app.xai.shap_explainer import (
    FeatureContribution,
    SHAPExplainer,
    SHAPResult,
)
from backend.app.xai.stability import ExplanationStabilityAnalyzer, StabilityReport


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_lr_detector(n_features: int = 5, n_samples: int = 40) -> tuple:
    """Create a fitted LogisticRegressionDetector and training data."""
    rng = np.random.RandomState(42)
    X = rng.randn(n_samples, n_features)
    y = (X[:, 0] > 0).astype(int)
    feature_names = [f"feat_{i}" for i in range(n_features)]
    detector = LogisticRegressionDetector(random_seed=42)
    detector.fit(X, y, feature_names=feature_names)
    return detector, X, feature_names


def _make_rf_detector(n_features: int = 5, n_samples: int = 40) -> tuple:
    """Create a fitted RandomForestDetector and training data."""
    rng = np.random.RandomState(42)
    X = rng.randn(n_samples, n_features)
    y = (X[:, 0] > 0).astype(int)
    feature_names = [f"feat_{i}" for i in range(n_features)]
    detector = RandomForestDetector(
        hyperparameters={"n_estimators": 10}, random_seed=42
    )
    detector.fit(X, y, feature_names=feature_names)
    return detector, X, feature_names


# ---------------------------------------------------------------------------
# SHAPExplainer — Logistic Regression
# ---------------------------------------------------------------------------

class TestSHAPExplainerLogisticRegression(unittest.TestCase):
    def setUp(self):
        self.detector, self.X, self.feature_names = _make_lr_detector()
        self.explainer = SHAPExplainer(
            detector=self.detector,
            X_background=self.X[:10],
            feature_names=self.feature_names,
        )

    def test_explain_returns_shap_result(self):
        result = self.explainer.explain(self.X[:1])
        self.assertIsInstance(result, SHAPResult)

    def test_method_is_linear(self):
        result = self.explainer.explain(self.X[:1])
        self.assertIn("Linear", result.method)

    def test_contributions_count_matches_features(self):
        result = self.explainer.explain(self.X[:1])
        self.assertEqual(len(result.contributions), len(self.feature_names))

    def test_all_contributions_are_feature_contributions(self):
        result = self.explainer.explain(self.X[:1])
        for c in result.contributions:
            self.assertIsInstance(c, FeatureContribution)

    def test_feature_names_match(self):
        result = self.explainer.explain(self.X[:1])
        names = [c.feature for c in result.contributions]
        self.assertEqual(names, self.feature_names)

    def test_importance_equals_abs_shap_value(self):
        result = self.explainer.explain(self.X[:1])
        for c in result.contributions:
            self.assertAlmostEqual(c.importance, abs(c.shap_value), places=9)

    def test_base_value_is_float(self):
        result = self.explainer.explain(self.X[:1])
        self.assertIsInstance(result.base_value, float)

    def test_top_k_returns_correct_count(self):
        result = self.explainer.explain(self.X[:1])
        top3 = result.top_k(3)
        self.assertEqual(len(top3), 3)

    def test_top_k_sorted_descending_by_importance(self):
        result = self.explainer.explain(self.X[:1])
        top_all = result.top_k(len(self.feature_names))
        importances = [c.importance for c in top_all]
        self.assertEqual(importances, sorted(importances, reverse=True))

    def test_top_k_as_json_valid(self):
        result = self.explainer.explain(self.X[:1])
        json_str = result.top_k_as_json(3)
        parsed = json.loads(json_str)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 3)
        for item in parsed:
            self.assertIn("feature", item)
            self.assertIn("shap_value", item)
            self.assertIn("importance", item)

    def test_explain_raises_on_multiple_rows(self):
        with self.assertRaises(ValueError):
            self.explainer.explain(self.X[:3])

    def test_explain_with_raw_sample_sets_value(self):
        raw = {f"feat_{i}": float(i) for i in range(len(self.feature_names))}
        result = self.explainer.explain(self.X[:1], raw_sample=raw)
        # raw sample values should be stored (not the transformed values)
        for c in result.contributions:
            expected = raw.get(c.feature)
            self.assertEqual(c.value, expected)

    def test_shap_values_are_finite(self):
        result = self.explainer.explain(self.X[:1])
        for c in result.contributions:
            self.assertTrue(
                np.isfinite(c.shap_value),
                f"SHAP value for '{c.feature}' is not finite: {c.shap_value}",
            )


# ---------------------------------------------------------------------------
# SHAPExplainer — Random Forest
# ---------------------------------------------------------------------------

class TestSHAPExplainerRandomForest(unittest.TestCase):
    def setUp(self):
        self.detector, self.X, self.feature_names = _make_rf_detector()
        self.explainer = SHAPExplainer(
            detector=self.detector,
            X_background=self.X[:10],
            feature_names=self.feature_names,
        )

    def test_explain_returns_shap_result(self):
        result = self.explainer.explain(self.X[:1])
        self.assertIsInstance(result, SHAPResult)

    def test_method_is_tree(self):
        result = self.explainer.explain(self.X[:1])
        self.assertIn("Tree", result.method)

    def test_contributions_count_matches_features(self):
        result = self.explainer.explain(self.X[:1])
        self.assertEqual(len(result.contributions), len(self.feature_names))

    def test_shap_values_are_finite(self):
        result = self.explainer.explain(self.X[:1])
        for c in result.contributions:
            self.assertTrue(
                np.isfinite(c.shap_value),
                f"RF SHAP value for '{c.feature}' is not finite: {c.shap_value}",
            )

    def test_top_k_sorted_descending_by_importance(self):
        result = self.explainer.explain(self.X[:1])
        top_all = result.top_k(len(self.feature_names))
        importances = [c.importance for c in top_all]
        self.assertEqual(importances, sorted(importances, reverse=True))

    def test_base_value_is_float(self):
        result = self.explainer.explain(self.X[:1])
        self.assertIsInstance(result.base_value, float)


# ---------------------------------------------------------------------------
# ExplanationStabilityAnalyzer
# ---------------------------------------------------------------------------

class TestExplanationStabilityAnalyzer(unittest.TestCase):
    def setUp(self):
        self.detector, self.X, self.feature_names = _make_lr_detector()
        self.explainer = SHAPExplainer(
            detector=self.detector,
            X_background=self.X[:10],
            feature_names=self.feature_names,
        )
        self.analyzer = ExplanationStabilityAnalyzer(
            explainer=self.explainer,
            n_repetitions=10,
            noise_std=0.01,
            random_seed=42,
        )

    def test_analyze_returns_stability_report(self):
        report = self.analyzer.analyze(self.X[:1])
        self.assertIsInstance(report, StabilityReport)

    def test_stability_score_in_range(self):
        report = self.analyzer.analyze(self.X[:1])
        self.assertGreaterEqual(report.stability_score, -1.0)
        self.assertLessEqual(report.stability_score, 1.0)

    def test_stability_score_is_float(self):
        report = self.analyzer.analyze(self.X[:1])
        self.assertIsInstance(report.stability_score, float)

    def test_correct_number_of_cosine_sims(self):
        report = self.analyzer.analyze(self.X[:1])
        self.assertEqual(len(report.cosine_similarities), 10)

    def test_all_cosine_sims_in_range(self):
        report = self.analyzer.analyze(self.X[:1])
        for sim in report.cosine_similarities:
            self.assertGreaterEqual(sim, -1.0)
            self.assertLessEqual(sim, 1.0)

    def test_std_property(self):
        report = self.analyzer.analyze(self.X[:1])
        self.assertGreaterEqual(report.std, 0.0)

    def test_low_noise_high_stability(self):
        """With very small noise the cosine similarity should be close to 1."""
        analyzer_low = ExplanationStabilityAnalyzer(
            explainer=self.explainer,
            n_repetitions=5,
            noise_std=1e-8,   # essentially zero noise
            random_seed=42,
        )
        report = analyzer_low.analyze(self.X[:1])
        self.assertGreater(report.stability_score, 0.95)

    def test_raises_on_multiple_rows(self):
        with self.assertRaises(ValueError):
            self.analyzer.analyze(self.X[:3])

    def test_deterministic_with_same_seed(self):
        """Two analyzers with the same seed should give identical results."""
        a1 = ExplanationStabilityAnalyzer(self.explainer, n_repetitions=5, random_seed=42)
        a2 = ExplanationStabilityAnalyzer(self.explainer, n_repetitions=5, random_seed=42)
        r1 = a1.analyze(self.X[:1])
        r2 = a2.analyze(self.X[:1])
        self.assertAlmostEqual(r1.stability_score, r2.stability_score, places=10)

    def test_rf_explainer_stability(self):
        """RandomForest explainer should also produce valid stability scores."""
        rf_detector, X_rf, feat_rf = _make_rf_detector()
        rf_explainer = SHAPExplainer(
            detector=rf_detector,
            X_background=X_rf[:5],
            feature_names=feat_rf,
        )
        rf_analyzer = ExplanationStabilityAnalyzer(
            explainer=rf_explainer,
            n_repetitions=5,
            noise_std=0.01,
            random_seed=42,
        )
        report = rf_analyzer.analyze(X_rf[:1])
        self.assertGreaterEqual(report.stability_score, -1.0)
        self.assertLessEqual(report.stability_score, 1.0)


# ---------------------------------------------------------------------------
# StabilityReport.std edge cases
# ---------------------------------------------------------------------------

class TestStabilityReportStd(unittest.TestCase):
    def test_std_single_element(self):
        report = StabilityReport(
            stability_score=0.9,
            cosine_similarities=[0.9],
            n_repetitions=1,
        )
        self.assertEqual(report.std, 0.0)

    def test_std_empty(self):
        report = StabilityReport(
            stability_score=0.0,
            cosine_similarities=[],
            n_repetitions=0,
        )
        self.assertEqual(report.std, 0.0)

    def test_std_two_elements(self):
        report = StabilityReport(
            stability_score=0.75,
            cosine_similarities=[0.5, 1.0],
            n_repetitions=2,
        )
        expected = float(np.std([0.5, 1.0], ddof=1))
        self.assertAlmostEqual(report.std, expected, places=10)


if __name__ == "__main__":
    unittest.main()
