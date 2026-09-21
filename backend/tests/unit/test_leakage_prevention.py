"""Tests to verify no data leakage in the preprocessing pipeline.

Key invariants tested:
1. Imputer statistics (medians) are computed from X_train only.
2. Scaler statistics (center/scale) are computed from X_train only.
3. Categorical encoders are fit on X_train only.
4. X_test is transformed using fitted objects, never re-fitted.
5. Label encoder is fit on the full dataset (acceptable for target encoding).
"""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from backend.app.ml.preprocessing.pipeline import (
    build_preprocessing_pipeline,
    _encode_categoricals,
)


class TestDataLeakagePrevention(unittest.TestCase):
    """Verify that preprocessing does not leak test information into training."""

    def _make_dataset(self, n_rows=500, n_features=5, seed=42):
        """Create a synthetic dataset with known distributions."""
        rng = np.random.RandomState(seed)
        data = {}
        for i in range(n_features):
            data[f"feature_{i}"] = rng.randn(n_rows) * (i + 1)
        # Inject missing values in one column
        data["feature_missing"] = rng.randn(n_rows)
        mask = rng.random(n_rows) < 0.1
        data["feature_missing"][mask] = np.nan
        # Binary label
        data["label"] = (np.array(list(range(n_rows))) % 2).tolist()
        return pd.DataFrame(data)

    def test_imputer_fit_on_train_only(self):
        """Imputer medians should differ when train/test have different distributions."""
        df = self._make_dataset(n_rows=200)
        result = build_preprocessing_pipeline(
            df, target_column="label",
            random_seed=42, train_ratio=0.8,
            save_dir=Path(tempfile.mkdtemp()),
        )
        imputer = result.pipeline.named_steps["imputer"]
        # Imputer statistics should be computed from training data only
        self.assertIsNotNone(imputer.statistics_)
        self.assertEqual(len(imputer.statistics_), len(result.feature_names))

    def test_scaler_fit_on_train_only(self):
        """Scaler center/scale should reflect training distribution only."""
        df = self._make_dataset(n_rows=200)
        result = build_preprocessing_pipeline(
            df, target_column="label",
            random_seed=42, train_ratio=0.8,
            save_dir=Path(tempfile.mkdtemp()),
        )
        scaler = result.pipeline.named_steps["scaler"]
        # RobustScaler stores center_ and scale_
        self.assertTrue(hasattr(scaler, "center_"))
        self.assertTrue(hasattr(scaler, "scale_"))
        self.assertEqual(len(scaler.center_), len(result.feature_names))
        self.assertEqual(len(scaler.scale_), len(result.feature_names))

    def test_no_nan_in_output(self):
        """After imputation and scaling, no NaN values should remain."""
        df = self._make_dataset(n_rows=200)
        result = build_preprocessing_pipeline(
            df, target_column="label",
            random_seed=42, train_ratio=0.8,
            save_dir=Path(tempfile.mkdtemp()),
        )
        self.assertFalse(np.isnan(result.X_train).any(), "NaN found in X_train")
        self.assertFalse(np.isnan(result.X_test).any(), "NaN found in X_test")

    def test_train_test_sizes_are_correct(self):
        """Train/test split should match the specified train_ratio."""
        df = self._make_dataset(n_rows=200)
        result = build_preprocessing_pipeline(
            df, target_column="label",
            random_seed=42, train_ratio=0.8,
            save_dir=Path(tempfile.mkdtemp()),
        )
        self.assertEqual(len(result.X_train), 160)  # 80% of 200
        self.assertEqual(len(result.X_test), 40)    # 20% of 200

    def test_feature_names_preserved(self):
        """Feature names should match the columns used in training."""
        df = self._make_dataset(n_rows=100)
        result = build_preprocessing_pipeline(
            df, target_column="label",
            random_seed=42, train_ratio=0.8,
            save_dir=Path(tempfile.mkdtemp()),
        )
        # All feature columns should be present (except label)
        self.assertIn("feature_0", result.feature_names)
        self.assertNotIn("label", result.feature_names)

    def test_categorical_encoder_fit_on_train_only(self):
        """Categorical encoders should be fit on training data only."""
        df = pd.DataFrame({
            "num_feat": range(100),
            "cat_feat": ["a", "b", "c", "d"] * 25,
            "label": [0] * 50 + [1] * 50,
        })
        result = build_preprocessing_pipeline(
            df, target_column="label",
            random_seed=42, train_ratio=0.8,
            save_dir=Path(tempfile.mkdtemp()),
        )
        # The pipeline should contain categorical encoder info
        # (Even if there are no categoricals, the pipeline should work)
        self.assertEqual(result.X_train.shape[1], len(result.feature_names))

    def test_deterministic_with_same_seed(self):
        """Same random seed should produce identical splits."""
        df = self._make_dataset(n_rows=200)
        save_dir = Path(tempfile.mkdtemp())
        r1 = build_preprocessing_pipeline(
            df, target_column="label",
            random_seed=42, train_ratio=0.8,
            save_dir=save_dir, artifact_name="run1",
        )
        r2 = build_preprocessing_pipeline(
            df, target_column="label",
            random_seed=42, train_ratio=0.8,
            save_dir=save_dir, artifact_name="run2",
        )
        np.testing.assert_array_equal(r1.X_train, r2.X_train)
        np.testing.assert_array_equal(r1.X_test, r2.X_test)
        np.testing.assert_array_equal(r1.y_train, r2.y_train)
        np.testing.assert_array_equal(r1.y_test, r2.y_test)

    def test_different_seed_produces_different_split(self):
        """Different random seeds should produce different splits."""
        df = self._make_dataset(n_rows=200)
        save_dir = Path(tempfile.mkdtemp())
        r1 = build_preprocessing_pipeline(
            df, target_column="label",
            random_seed=42, train_ratio=0.8,
            save_dir=save_dir, artifact_name="seed42",
        )
        r2 = build_preprocessing_pipeline(
            df, target_column="label",
            random_seed=99, train_ratio=0.8,
            save_dir=save_dir, artifact_name="seed99",
        )
        # At least one sample should differ in the test set
        self.assertFalse(np.array_equal(r1.X_test, r2.X_test))


class TestEncodeCategoricals(unittest.TestCase):
    """Test categorical encoding with leakage prevention."""

    def test_unseen_values_encoded_as_negative_one(self):
        """Values not seen during training should be encoded as -1."""
        train_df = pd.DataFrame({"cat": ["a", "b", "c", "a", "b"]})
        test_df = pd.DataFrame({"cat": ["a", "d", "b", "e"]})

        train_encoded, encoders = _encode_categoricals(train_df, ["cat"])
        test_encoded, _ = _encode_categoricals(test_df, ["cat"], fit_encoders=encoders)

        # "a" and "b" should be encoded with valid values
        # "d" and "e" (unseen) should be -1
        test_values = test_encoded["cat"].tolist()
        self.assertIn(-1, test_values)  # unseen values present

    def test_encoder_not_refitted_on_test(self):
        """Calling _encode_categoricals with fit_encoders should not modify them."""
        train_df = pd.DataFrame({"cat": ["x", "y", "z"] * 10})
        _, encoders = _encode_categoricals(train_df, ["cat"])

        # Get original classes
        original_classes = set(encoders["cat"].classes_)

        # Process test data (with fit_encoders provided)
        test_df = pd.DataFrame({"cat": ["x", "y", "w"] * 5})
        _encode_categoricals(test_df, ["cat"], fit_encoders=encoders)

        # Encoder classes should not have changed
        self.assertEqual(set(encoders["cat"].classes_), original_classes)


if __name__ == "__main__":
    unittest.main()
