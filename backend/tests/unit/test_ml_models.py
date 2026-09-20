"""Unit tests for ML models (Logistic Regression, Random Forest, BaseDetector)."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
from sklearn.datasets import make_classification

from backend.app.core.exceptions import ModelTrainingError
from backend.app.ml.models.base import BaseDetector
from backend.app.ml.models.logistic_regression import LogisticRegressionDetector
from backend.app.ml.models.random_forest import RandomForestDetector


class TestMLModels(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        X, y = make_classification(
            n_samples=200,
            n_features=6,
            n_informative=4,
            n_redundant=1,
            n_classes=2,
            random_state=42,
        )
        self.X_train = X[:150]
        self.y_train = y[:150]
        self.X_test = X[150:]
        self.y_test = y[150:]
        self.feature_names = [f"feat_{i}" for i in range(6)]

    def test_logistic_regression_fit_predict(self):
        model = LogisticRegressionDetector(random_seed=42)
        self.assertFalse(model.is_fitted)

        # Unfitted prediction must raise error
        with self.assertRaises(ModelTrainingError):
            model.predict(self.X_test)

        model.fit(self.X_train, self.y_train, feature_names=self.feature_names)
        self.assertTrue(model.is_fitted)

        preds = model.predict(self.X_test)
        self.assertEqual(len(preds), len(self.X_test))
        self.assertTrue(set(preds).issubset({0, 1}))

        probs = model.predict_proba(self.X_test)
        self.assertEqual(probs.shape, (len(self.X_test), 2))
        np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-5)

        # Coefficients
        self.assertIsNotNone(model.coefficients)
        self.assertIsNotNone(model.intercept)
        feat_weights = model.get_feature_coefficients()
        self.assertEqual(len(feat_weights), 6)
        self.assertIn("feat_0", feat_weights)

    def test_logistic_regression_save_load(self):
        model = LogisticRegressionDetector(random_seed=42)
        model.fit(self.X_train, self.y_train, feature_names=self.feature_names)
        preds_orig = model.predict(self.X_test)

        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "lr_model.joblib"
            model.save(save_path)
            self.assertTrue(save_path.exists())

            loaded = LogisticRegressionDetector.load(save_path)
            self.assertTrue(loaded.is_fitted)
            self.assertEqual(loaded.feature_names, self.feature_names)
            preds_loaded = loaded.predict(self.X_test)
            np.testing.assert_array_equal(preds_orig, preds_loaded)

    def test_random_forest_fit_predict(self):
        model = RandomForestDetector(
            hyperparameters={"n_estimators": 20, "max_depth": 5},
            random_seed=42,
        )
        self.assertFalse(model.is_fitted)

        with self.assertRaises(ModelTrainingError):
            model.predict_proba(self.X_test)

        model.fit(self.X_train, self.y_train, feature_names=self.feature_names)
        self.assertTrue(model.is_fitted)

        preds = model.predict(self.X_test)
        self.assertEqual(len(preds), len(self.X_test))

        probs = model.predict_proba(self.X_test)
        self.assertEqual(probs.shape, (len(self.X_test), 2))
        np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-5)

        # Feature importances
        importances = model.feature_importances_
        self.assertEqual(len(importances), 6)
        self.assertAlmostEqual(float(importances.sum()), 1.0, places=4)
        imp_dict = model.get_feature_importances()
        self.assertEqual(len(imp_dict), 6)

    def test_random_forest_save_load(self):
        model = RandomForestDetector(
            hyperparameters={"n_estimators": 20, "max_depth": 5},
            random_seed=42,
        )
        model.fit(self.X_train, self.y_train, feature_names=self.feature_names)
        probs_orig = model.predict_proba(self.X_test)

        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "rf_model.joblib"
            model.save(save_path)
            self.assertTrue(save_path.exists())

            loaded = RandomForestDetector.load(save_path)
            self.assertTrue(loaded.is_fitted)
            probs_loaded = loaded.predict_proba(self.X_test)
            np.testing.assert_allclose(probs_orig, probs_loaded, atol=1e-5)


if __name__ == "__main__":
    unittest.main()
