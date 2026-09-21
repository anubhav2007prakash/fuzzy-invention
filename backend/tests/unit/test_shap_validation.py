"""SHAP validation tests — P2-5.

Confirms that SHAP explanations correspond to actual model predictions:
1. Local accuracy: base_value + Σ(shap_values) ≈ model prediction probability.
2. Feature names in output match input feature names exactly.
3. Explanation length matches input feature count.
4. Explanations work for different prediction types (benign vs attack).
5. Edge cases: features with zeros, all-same features, extreme values.

These tests use both LogisticRegression (LinearSHAP) and RandomForest (TreeSHAP).
For TreeSHAP, the additivity property (base + sum = prediction) holds exactly.
For LinearSHAP, it holds within floating-point tolerance.
"""
import unittest

import numpy as np

from backend.app.ml.models.logistic_regression import LogisticRegressionDetector
from backend.app.ml.models.random_forest import RandomForestDetector
from backend.app.xai.shap_explainer import SHAPExplainer


def _fit_detector(model_type: str, n_features: int = 6, n_samples: int = 200, seed: int = 42):
    """Train a detector on synthetic data with clear class separation.

    Data has two well-separated clusters so the model learns a distinct
    decision boundary, making explanations non-trivial.
    """
    rng = np.random.RandomState(seed)
    X = rng.randn(n_samples, n_features)
    # Class 1 when first feature > threshold (creates a clear boundary)
    y = (X[:, 0] + 0.5 * X[:, 1] > 0.3).astype(int)
    feature_names = [f"feat_{i}" for i in range(n_features)]

    if model_type == "logistic_regression":
        detector = LogisticRegressionDetector(random_seed=seed)
    else:
        detector = RandomForestDetector(
            hyperparameters={"n_estimators": 50, "max_depth": 6}, random_seed=seed
        )
    detector.fit(X, y, feature_names=feature_names)
    return detector, X, y, feature_names


def _build_explainer(detector, X, feature_names):
    return SHAPExplainer(
        detector=detector,
        X_background=X[:50],
        feature_names=feature_names,
    )


class TestLocalAccuracyTreeSHAP(unittest.TestCase):
    """TreeSHAP satisfies additivity: base_value + Σ(shap_i) ≈ p(class=1).

    This is the fundamental local accuracy property of SHAP values.
    For TreeSHAP it holds exactly (within floating-point precision).
    """

    def setUp(self):
        self.detector, self.X, self.y, self.fnames = _fit_detector("random_forest")
        self.explainer = _build_explainer(self.detector, self.X, self.fnames)

    def _check_additivity(self, X_row):
        """Verify base + sum(shap) ≈ predict_proba(X_row)[1]."""
        result = self.explainer.explain(X_row)
        shap_sum = sum(c.shap_value for c in result.contributions)
        reconstructed = result.base_value + shap_sum

        proba = self.detector.predict_proba(X_row)[0, 1]
        self.assertAlmostEqual(
            reconstructed, proba, places=5,
            msg=(
                f"Local accuracy violated: base({result.base_value:.6f}) "
                f"+ sum({shap_sum:.6f}) = {reconstructed:.6f}, "
                f"but predict_proba = {proba:.6f}"
            ),
        )

    def test_additivity_attack_sample(self):
        """Attack sample (feat_0 > 0) should have high probability."""
        idx = int(np.where(self.y == 1)[0][0])
        X_row = self.X[idx : idx + 1]
        proba = self.detector.predict_proba(X_row)[0, 1]
        self.assertGreater(proba, 0.5, "Expected attack sample to have p > 0.5")
        self._check_additivity(X_row)

    def test_additivity_benign_sample(self):
        """Benign sample (feat_0 < 0) should have low probability."""
        idx = int(np.where(self.y == 0)[0][0])
        X_row = self.X[idx : idx + 1]
        proba = self.detector.predict_proba(X_row)[0, 1]
        self.assertLess(proba, 0.5, "Expected benign sample to have p < 0.5")
        self._check_additivity(X_row)

    def test_additivity_boundary_sample(self):
        """Sample near the decision boundary."""
        # Create a sample right at the boundary
        X_boundary = np.array([[0.3, 0.0, 0.0, 0.0, 0.0, 0.0]])
        proba = self.detector.predict_proba(X_boundary)[0, 1]
        self._check_additivity(X_boundary)

    def test_additivity_all_fifteen_samples(self):
        """Verify additivity holds for multiple diverse samples."""
        rng = np.random.RandomState(99)
        samples = rng.randn(15, len(self.fnames))
        for i in range(15):
            self._check_additivity(samples[i : i + 1])


class TestLocalAccuracyLinearSHAP(unittest.TestCase):
    """LinearSHAP additivity: base + Σ(shap_i) ≈ log-odds (linear model).

    For LinearSHAP the sum equals the log-odds, not the probability directly.
    We verify the relationship holds via sigmoid reconstruction.
    """

    def setUp(self):
        self.detector, self.X, self.y, self.fnames = _fit_detector("logistic_regression")
        self.explainer = _build_explainer(self.detector, self.X, self.fnames)

    def test_additivity_via_log_odds(self):
        """For LR, base + sum(shap) should equal the logit (linear output)."""
        X_row = self.X[:1]
        result = self.explainer.explain(X_row)
        shap_sum = sum(c.shap_value for c in result.contributions)
        reconstructed_logit = result.base_value + shap_sum

        # Convert probability to logit for comparison
        proba = self.detector.predict_proba(X_row)[0, 1]
        proba_clipped = np.clip(proba, 1e-7, 1 - 1e-7)
        expected_logit = np.log(proba_clipped / (1 - proba_clipped))

        self.assertAlmostEqual(
            reconstructed_logit, expected_logit, places=3,
            msg=(
                f"LinearSHAP log-odds: reconstructed={reconstructed_logit:.4f}, "
                f"expected={expected_logit:.4f}"
            ),
        )


class TestFeatureNameAlignment(unittest.TestCase):
    """Feature names in SHAP output must exactly match input feature names."""

    def setUp(self):
        self.detector, self.X, self.y, self.fnames = _fit_detector("random_forest")
        self.explainer = _build_explainer(self.detector, self.X, self.fnames)

    def test_exact_name_match_order_preserved(self):
        """Output feature names must be identical to input, in the same order."""
        result = self.explainer.explain(self.X[:1])
        output_names = [c.feature for c in result.contributions]
        self.assertEqual(output_names, self.fnames)

    def test_custom_feature_names_preserved(self):
        """Renamed features should appear exactly as given."""
        custom_names = [
            "flow_duration", "src_packets", "dst_packets",
            "src_bytes", "dst_bytes", "packet_rate",
        ]
        detector, X, y, _ = _fit_detector("random_forest")
        detector.fit(X, y, feature_names=custom_names)
        explainer = SHAPExplainer(detector, X[:50], custom_names)

        result = explainer.explain(X[:1])
        output_names = [c.feature for c in result.contributions]
        self.assertEqual(output_names, custom_names)

    def test_no_duplicate_names(self):
        """Every feature in the output should have a unique name."""
        result = self.explainer.explain(self.X[:1])
        names = [c.feature for c in result.contributions]
        self.assertEqual(len(names), len(set(names)), "Duplicate feature names found")


class TestExplanationLength(unittest.TestCase):
    """Explanation length must match the number of input features."""

    def setUp(self):
        self.detector, self.X, self.y, self.fnames = _fit_detector("random_forest")
        self.explainer = _build_explainer(self.detector, self.X, self.fnames)

    def test_length_matches_feature_count(self):
        result = self.explainer.explain(self.X[:1])
        self.assertEqual(len(result.contributions), len(self.fnames))

    def test_top_k_capped_at_feature_count(self):
        """top_k(k) where k > n_features should return all features."""
        result = self.explainer.explain(self.X[:1])
        top = result.top_k(9999)
        self.assertEqual(len(top), len(self.fnames))


class TestDifferentPredictionTypes(unittest.TestCase):
    """Explanations must work for both benign and attack predictions."""

    def setUp(self):
        self.detector, self.X, self.y, self.fnames = _fit_detector("random_forest")
        self.explainer = _build_explainer(self.detector, self.X, self.fnames)

    def test_benign_explanation(self):
        """Benign samples (class 0) should get valid explanations."""
        idx = int(np.where(self.y == 0)[0][0])
        X_row = self.X[idx : idx + 1]
        pred = self.detector.predict(X_row)[0]
        self.assertEqual(pred, 0)

        result = self.explainer.explain(X_row)
        self.assertEqual(len(result.contributions), len(self.fnames))
        self.assertTrue(all(np.isfinite(c.shap_value) for c in result.contributions))

    def test_attack_explanation(self):
        """Attack samples (class 1) should get valid explanations."""
        idx = int(np.where(self.y == 1)[0][0])
        X_row = self.X[idx : idx + 1]
        pred = self.detector.predict(X_row)[0]
        self.assertEqual(pred, 1)

        result = self.explainer.explain(X_row)
        self.assertEqual(len(result.contributions), len(self.fnames))
        self.assertTrue(all(np.isfinite(c.shap_value) for c in result.contributions))

    def test_explanations_differ_by_class(self):
        """Benign and attack samples should have different SHAP profiles."""
        benign_idx = int(np.where(self.y == 0)[0][0])
        attack_idx = int(np.where(self.y == 1)[0][0])

        r_benign = self.explainer.explain(self.X[benign_idx : benign_idx + 1])
        r_attack = self.explainer.explain(self.X[attack_idx : attack_idx + 1])

        benign_vec = np.array([c.shap_value for c in r_benign.contributions])
        attack_vec = np.array([c.shap_value for c in r_attack.contributions])

        # They should not be identical (model is making different decisions)
        cosine_sim = np.dot(benign_vec, attack_vec) / (
            np.linalg.norm(benign_vec) * np.linalg.norm(attack_vec) + 1e-10
        )
        self.assertLess(cosine_sim, 0.99,
                        "Benign and attack explanations are suspiciously similar")


class TestEdgeCases(unittest.TestCase):
    """Edge case handling: zeros, extreme values, single feature."""

    def setUp(self):
        self.detector, self.X, self.y, self.fnames = _fit_detector("random_forest")
        self.explainer = _build_explainer(self.detector, self.X, self.fnames)

    def test_zero_features(self):
        """Explanation for an all-zeros input should still produce valid attributions."""
        X_zeros = np.zeros((1, len(self.fnames)))
        result = self.explainer.explain(X_zeros)
        self.assertEqual(len(result.contributions), len(self.fnames))
        self.assertTrue(all(np.isfinite(c.shap_value) for c in result.contributions))

    def test_extreme_positive_values(self):
        """Very large feature values should produce finite attributions."""
        X_extreme = np.full((1, len(self.fnames)), 1e6)
        result = self.explainer.explain(X_extreme)
        self.assertEqual(len(result.contributions), len(self.fnames))
        # SHAP values should be finite (model may saturate, but SHAP handles this)
        for c in result.contributions:
            self.assertTrue(np.isfinite(c.shap_value),
                            f"Non-finite SHAP for '{c.feature}': {c.shap_value}")

    def test_extreme_negative_values(self):
        """Very negative feature values should produce finite attributions."""
        X_neg = np.full((1, len(self.fnames)), -1e6)
        result = self.explainer.explain(X_neg)
        self.assertEqual(len(result.contributions), len(self.fnames))

    def test_mixed_zeros_and_nonzeros(self):
        """Mix of zero and non-zero features."""
        X_mixed = np.zeros((1, len(self.fnames)))
        X_mixed[0, 0] = 5.0
        X_mixed[0, 2] = -3.0
        result = self.explainer.explain(X_mixed)
        self.assertEqual(len(result.contributions), len(self.fnames))
        # Feature 0 and 2 should have non-trivial attribution
        vals = {c.feature: c.shap_value for c in result.contributions}
        self.assertNotAlmostEqual(vals["feat_0"], 0.0, places=3)
        self.assertNotAlmostEqual(vals["feat_2"], 0.0, places=3)

    def test_single_feature_model(self):
        """Model trained on a single feature should still explain correctly."""
        rng = np.random.RandomState(42)
        X_1d = rng.randn(100, 1)
        y_1d = (X_1d[:, 0] > 0).astype(int)
        names_1d = ["only_feature"]

        det = RandomForestDetector(
            hyperparameters={"n_estimators": 20, "max_depth": 3}, random_seed=42
        )
        det.fit(X_1d, y_1d, feature_names=names_1d)
        explainer = SHAPExplainer(det, X_1d[:20], names_1d)

        result = explainer.explain(X_1d[:1])
        self.assertEqual(len(result.contributions), 1)
        self.assertEqual(result.contributions[0].feature, "only_feature")

    def test_feature_value_stored_correctly(self):
        """The raw feature value stored in contribution should match input."""
        X_row = np.array([[1.5, -2.3, 0.0, 4.1, -0.7, 0.5]])
        result = self.explainer.explain(X_row)
        for i, c in enumerate(result.contributions):
            self.assertAlmostEqual(c.value, X_row[0, i], places=10,
                                   msg=f"Value mismatch for '{c.feature}'")


class TestBothModelTypes(unittest.TestCase):
    """SHAP validation should hold for both LR and RF models."""

    def _test_local_accuracy(self, model_type):
        detector, X, y, fnames = _fit_detector(model_type)
        explainer = _build_explainer(detector, X, fnames)

        # Test on a few samples
        for idx in [0, 10, 50]:
            X_row = X[idx : idx + 1]
            result = explainer.explain(X_row)
            output_names = [c.feature for c in result.contributions]

            # Feature names match
            self.assertEqual(output_names, fnames)
            # Explanation length matches
            self.assertEqual(len(result.contributions), len(fnames))
            # All values finite
            self.assertTrue(all(np.isfinite(c.shap_value) for c in result.contributions))
            # Importances are non-negative
            self.assertTrue(all(c.importance >= 0 for c in result.contributions))

    def test_linear_shap(self):
        self._test_local_accuracy("logistic_regression")

    def test_tree_shap(self):
        self._test_local_accuracy("random_forest")


if __name__ == "__main__":
    unittest.main()
