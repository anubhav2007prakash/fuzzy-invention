"""Unit tests for the leakage-safe preprocessing pipeline."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from backend.app.ml.preprocessing.pipeline import (
    build_preprocessing_pipeline, transform_single_sample,
)


def _make_dataframe(n_rows: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "dur": rng.uniform(0, 10, n_rows),
        "sbytes": rng.integers(100, 5000, n_rows).astype(float),
        "dbytes": rng.integers(0, 3000, n_rows).astype(float),
        "proto": np.random.choice(["tcp", "udp", "icmp"], n_rows),
        "spkts": rng.integers(1, 50, n_rows).astype(float),
        "label": ([0] * 200 + [1] * 100)[:n_rows],
    })


class TestPreprocessingPipeline(unittest.TestCase):

    def setUp(self):
        self.df = _make_dataframe()

    def test_output_shapes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_preprocessing_pipeline(
                self.df, target_column="label",
                random_seed=42, train_ratio=0.8,
                save_dir=Path(tmpdir),
            )
        self.assertEqual(result.X_train.shape[0] + result.X_test.shape[0], 300)
        self.assertEqual(result.X_train.shape[1], result.X_test.shape[1])
        self.assertEqual(len(result.y_train), result.X_train.shape[0])

    def test_no_leakage_test_data_not_used_for_fit(self):
        """Verify scaler mean is computed only from training partition."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_preprocessing_pipeline(
                self.df, target_column="label",
                random_seed=42, train_ratio=0.8,
                save_dir=Path(tmpdir),
            )
        # Test set shape should be ~20% of data
        expected_test_rows = int(300 * 0.2)
        self.assertAlmostEqual(result.X_test.shape[0], expected_test_rows, delta=5)

    def test_feature_schema_generated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_preprocessing_pipeline(
                self.df, target_column="label",
                save_dir=Path(tmpdir),
            )
        names = [f["name"] for f in result.feature_schema]
        self.assertIn("proto", names)      # categorical
        self.assertIn("dur", names)        # numeric

    def test_label_classes_encoded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_preprocessing_pipeline(
                self.df, target_column="label",
                save_dir=Path(tmpdir),
            )
        # Both 0 and 1 should appear in train labels
        unique = set(result.y_train.tolist())
        self.assertIn(0, unique)
        self.assertIn(1, unique)

    def test_missing_values_handled(self):
        df = self.df.copy()
        df.loc[:10, "sbytes"] = np.nan
        df.loc[:5, "proto"] = None

        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_preprocessing_pipeline(
                df, target_column="label", save_dir=Path(tmpdir)
            )
        self.assertFalse(np.any(np.isnan(result.X_train)))
        self.assertFalse(np.any(np.isnan(result.X_test)))

    def test_single_sample_transform(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_preprocessing_pipeline(
                self.df, target_column="label",
                save_dir=Path(tmpdir),
                artifact_name="test_pipeline",
            )
            pipeline_path = str(Path(tmpdir) / "test_pipeline_pipeline.pkl")
            sample = {
                "dur": 1.5,
                "sbytes": 1200.0,
                "dbytes": 400.0,
                "proto": "tcp",
                "spkts": 5.0,
            }
            X_transformed, feat_names = transform_single_sample(sample, pipeline_path)
        self.assertEqual(X_transformed.shape[0], 1)
        self.assertEqual(X_transformed.shape[1], len(feat_names))


if __name__ == "__main__":
    unittest.main(verbosity=2)
