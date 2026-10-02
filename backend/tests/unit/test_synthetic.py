"""Tests for the shared synthetic data generator."""
import numpy as np
import pandas as pd
import pytest

from backend.app.ml.data.synthetic import generate_flow_csv, generate_flow_dataset


def test_deterministic_for_same_seed():
    a = generate_flow_dataset(n_samples=200, random_state=42)
    b = generate_flow_dataset(n_samples=200, random_state=42)
    pd.testing.assert_frame_equal(a, b)


def test_missing_rate_inserts_nan_cells():
    df = generate_flow_dataset(n_samples=300, random_state=42, missing_rate=0.05)
    assert df.isna().sum().sum() > 0
    # label column itself stays intact
    assert df["label"].isna().sum() == 0


def test_attack_ratio_controls_class_balance():
    df = generate_flow_dataset(n_samples=1000, random_state=42, attack_ratio=0.5)
    assert abs(df["label"].mean() - 0.5) < 0.02


def test_shift_scale_changes_distribution():
    base = generate_flow_dataset(n_samples=1000, random_state=42, shift_scale=1.0)
    shifted = generate_flow_dataset(n_samples=1000, random_state=42, shift_scale=2.0)
    # larger shift_scale stretches benign flow durations (exponential scale)
    assert shifted["dur"].mean() > base["dur"].mean()


def test_invalid_arguments_raise():
    with pytest.raises(ValueError):
        generate_flow_dataset(n_samples=0)
    with pytest.raises(ValueError):
        generate_flow_dataset(attack_ratio=1.5)
    with pytest.raises(ValueError):
        generate_flow_dataset(missing_rate=1.0)


def test_csv_export_round_trip_and_label():
    content, filename = generate_flow_csv(n_samples=100, random_state=42)
    assert filename.endswith(".csv")
    df = pd.read_csv(pd.io.common.BytesIO(content))
    assert set(df.columns) >= {"label", "dur", "spkts"}
    assert set(df["label"].unique()) <= {0, 1}
