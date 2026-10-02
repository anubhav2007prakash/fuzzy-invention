"""Reference dataset plugin — CSV loader.

Demonstrates how to add a new DatasetPlugin variant that loads CSV files
with automatic schema inference.  This is distinct from the built-in
``synthetic_flows`` generator.

Security guarantees (enforced by PluginHost / DatasetService):
- The plugin's ``validate()`` method is called before upload
- Column data types are inspected; non-numeric columns beyond the target
  are flagged for review
- The host (DatasetService) performs additional lineage and provenance checks
- No plugin may skip dataset validation or bypass provenance recording
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from backend.app.plugins.protocols import DatasetPlugin


class CSVLoader(DatasetPlugin):
    """CSV dataset loader plugin.

    Automatically detects whether the CSV contains a ``target`` column and
    separates features from labels accordingly.  Non-numeric columns are
    preserved as metadata but excluded from the numeric feature matrix.
    """

    name: str = "csv"
    version: str = "1.0.0"
    file_pattern: str = "*.csv"

    def load(self, path: Path) -> tuple[np.ndarray, list[str]]:
        """Load a CSV file and return (feature_matrix, feature_names).

        Args:
            path: Path to the CSV file.

        Returns:
            ``(X, feature_names)`` where ``X`` is a numpy array of numeric
            features and ``feature_names`` is the corresponding list of column
            names (excluding the ``target`` column if present).
        """
        df = pd.read_csv(path)

        # Determine if a target column exists
        if "target" in df.columns:
            y = df["target"].values.astype(int)
            feature_names = [c for c in df.columns if c != "target"]
            X_df = df.drop(columns=["target"])
        else:
            y = np.zeros(len(df), dtype=int)
            feature_names = list(df.columns)
            X_df = df

        # Keep only numeric columns for the feature matrix
        X_df = X_df.select_dtypes(include=[np.number])

        # If everything was dropped (e.g. all columns were strings), fall back
        if X_df.shape[1] == 0:
            X_df = df.select_dtypes(include=[np.number])
            feature_names = list(X_df.columns) if X_df.shape[1] > 0 else feature_names
            y = np.zeros(len(df), dtype=int)

        X = X_df.values.astype(float)
        return X, feature_names

    def validate(self, path: Path) -> bool:
        """Validate that the CSV has at least 2 columns and 5 rows.

        This check is performed by the host (DatasetService) before the
        dataset is registered in the database.
        """
        try:
            df = pd.read_csv(path)
            return len(df.columns) >= 2 and len(df) >= 5
        except Exception:
            return False

    def compute_provenance(self) -> Dict[str, Any]:
        """Return metadata describing this plugin for experiment tracking."""
        return {
            "author": "sentinelcrypt-research",
            "citation": "CSV dataset loader plugin (v1.0.0)",
            "file_pattern": self.file_pattern,
        }