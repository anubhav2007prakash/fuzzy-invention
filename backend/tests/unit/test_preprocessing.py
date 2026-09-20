"""Unit tests for dataset validation — UNSW-NB15, CICIDS2017, generic CSV, and edge cases."""
from __future__ import annotations

import io
import unittest

import pandas as pd

from backend.app.ml.preprocessing.validators import (
    validate_dataset, UNSW_NB15_REQUIRED, UNSW_NB15_LABEL_COLS,
)
from backend.app.core.exceptions import InvalidDatasetError, UnsupportedFormatError


def _make_csv(columns: list[str], n_rows: int = 200, label_col: str = "label") -> bytes:
    """Build a minimal CSV with the given columns."""
    data = {c: (list(range(n_rows)) if c != label_col else [0] * 100 + [1] * 100) for c in columns}
    df = pd.DataFrame(data)
    return df.to_csv(index=False).encode("utf-8")


class TestDatasetValidator(unittest.TestCase):

    # ── Happy paths ───────────────────────────────────────────────────────────

    def test_unsw_nb15_detection(self):
        cols = UNSW_NB15_REQUIRED[:20] + ["label"]
        csv_bytes = _make_csv(cols)
        df, report = validate_dataset(csv_bytes, "unsw_test.csv")
        self.assertTrue(report.valid)
        self.assertEqual(report.detected_format, "UNSW-NB15")
        self.assertEqual(report.target_column, "label")
        self.assertEqual(report.row_count, 200)

    def test_generic_csv_with_label_column(self):
        cols = ["feature_a", "feature_b", "feature_c", "label"]
        csv_bytes = _make_csv(cols)
        df, report = validate_dataset(csv_bytes, "generic.csv")
        self.assertTrue(report.valid)
        self.assertEqual(report.detected_format, "GENERIC_CSV")
        self.assertEqual(report.target_column, "label")

    def test_custom_target_column(self):
        cols = ["feat1", "feat2", "my_class"]
        csv_bytes = _make_csv(cols, label_col="my_class")
        df, report = validate_dataset(csv_bytes, "custom.csv", custom_target_column="my_class")
        self.assertTrue(report.valid)
        self.assertEqual(report.target_column, "my_class")

    def test_label_distribution_computed(self):
        cols = ["f1", "f2", "label"]
        csv_bytes = _make_csv(cols, n_rows=200)
        df, report = validate_dataset(csv_bytes, "dist_test.csv")
        self.assertIn("0", report.label_distribution)
        self.assertIn("1", report.label_distribution)
        self.assertEqual(report.label_distribution["0"] + report.label_distribution["1"], 200)

    def test_missing_value_detection(self):
        data = {
            "dur": [1.0, None, 3.0] * 100,
            "sbytes": [10, 20, 30] * 100,
            "label": [0, 1, 0] * 100,
        }
        df = pd.DataFrame(data)
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        _, report = validate_dataset(csv_bytes, "missing.csv", custom_target_column="label")
        self.assertIn("dur", report.missing_value_counts)
        self.assertGreater(report.missing_value_counts["dur"], 0)

    # ── Error paths ───────────────────────────────────────────────────────────

    def test_non_csv_raises_unsupported(self):
        with self.assertRaises(UnsupportedFormatError):
            validate_dataset(b"not a csv", "data.json")

    def test_empty_file_raises_invalid(self):
        with self.assertRaises(UnsupportedFormatError):
            validate_dataset(b"", "empty.csv")

    def test_missing_custom_target_raises_invalid(self):
        cols = ["feat1", "feat2", "feat3"]
        csv_bytes = _make_csv(cols, label_col="feat3")
        with self.assertRaises(InvalidDatasetError):
            validate_dataset(csv_bytes, "no_label.csv", custom_target_column="nonexistent_col")

    def test_feature_count_excludes_label(self):
        cols = ["f1", "f2", "f3", "f4", "label"]
        csv_bytes = _make_csv(cols)
        _, report = validate_dataset(csv_bytes, "feat_count.csv")
        self.assertEqual(report.feature_count, 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
