"""Tests for research measurement primitives (research_metrics)."""
import numpy as np
import pytest

from backend.app.ml.evaluation.research_metrics import (
    classification_metrics,
    expected_calibration_error,
    flatten_numeric,
    paired_compare,
    summarize,
    time_median_ms,
    track_peak_memory_mb,
)


def test_classification_metrics_perfect_predictions():
    y_true = [0, 0, 1, 1]
    y_pred = [0, 0, 1, 1]
    y_prob = [0.1, 0.2, 0.8, 0.9]
    m = classification_metrics(y_true, y_pred, y_prob)
    assert m["f1"] == 1.0
    assert m["f1_macro"] == 1.0
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["pr_auc"] == 1.0
    # all-correct + high confidence ≠ perfect calibration in tiny samples:
    # ECE stays bounded but nonzero; calibration math is covered by the next test
    assert 0.0 <= m["ece"] <= 0.16
    assert 0 <= m["brier"] <= 0.03


def test_classification_metrics_includes_macro_and_pr_auc():
    y_true = [0, 0, 0, 1, 1, 1]
    y_pred = [0, 0, 1, 1, 1, 0]
    y_prob = [0.1, 0.2, 0.6, 0.9, 0.8, 0.4]
    m = classification_metrics(y_true, y_pred, y_prob)
    assert 0 <= m["f1"] <= 1
    assert 0 <= m["f1_macro"] <= 1
    assert 0 <= m["pr_auc"] <= 1
    assert 0 <= m["ece"] <= 1


def test_ece_is_low_for_well_calibrated_predictions():
    # draw labels FROM the stated confidence: accuracy in each bin ≈ confidence
    rng = np.random.RandomState(0)
    y_prob = np.tile([0.2, 0.8], 2000)
    y_true = rng.binomial(1, y_prob)
    assert expected_calibration_error(y_true, list(y_prob)) < 0.05


def test_ece_flags_underconfidence():
    # model is always right but only claims 0.8 → ECE ≈ 0.2
    y_true = [0, 1] * 100
    y_prob = [0.2, 0.8] * 100
    assert expected_calibration_error(y_true, y_prob) > 0.15


def test_ece_flags_overconfidence():
    # predicts 0.99 confidence but wrong half the time
    y_true = [0, 1] * 50
    y_prob = [0.99, 0.99] * 50
    assert expected_calibration_error(y_true, y_prob) > 0.4


def test_legacy_summarize_is_descriptive_and_does_not_infer_a_confidence_interval():
    vals = [1.0, 1.2, 0.8, 1.1, 0.9, 1.0]
    stats = summarize(vals)
    assert stats["n"] == 6
    assert stats["ci95_low"] is None and stats["ci95_high"] is None
    assert stats["min"] <= stats["mean"] <= stats["max"]


def test_summarize_handles_empty_and_single():
    empty = summarize([])
    assert empty["mean"] is None and empty["n"] == 0
    single = summarize([2.0])
    assert single["std"] == 0.0
    assert single["ci95_low"] is None and single["ci95_high"] is None


def test_paired_compare_detects_difference_and_effect():
    baseline = [0.80, 0.81, 0.79, 0.80, 0.82]
    treatment = [0.85, 0.87, 0.84, 0.86, 0.89]
    result = paired_compare(
        baseline,
        treatment,
        [f"trial-{i}" for i in range(len(baseline))],
        baseline_raw_data_ref="/baseline",
        treatment_raw_data_ref="/treatment",
        bootstrap_resamples=500,
    )
    assert result["design"] == "paired repeated trials"
    assert result["mean_difference_treatment_minus_baseline"] > 0.04
    assert abs(result["cohens_dz"]) > 1
    assert result["p_value"] is None
    assert result["raw_data_refs"] == ["/baseline", "/treatment"]


def test_paired_compare_rejects_unequal_groups_instead_of_truncating():
    with pytest.raises(ValueError, match="equal lengths"):
        paired_compare(
            [1.0, 2.0],
            [2.0],
            ["trial-1", "trial-2"],
            baseline_raw_data_ref="/baseline",
            treatment_raw_data_ref="/treatment",
            bootstrap_resamples=500,
        )


def test_track_peak_memory_mb_measures_allocations():
    with track_peak_memory_mb() as mem:
        _ = np.zeros(1_000_000)  # ~8 MB
    assert mem["peak_mb"] > 5


def test_time_median_ms_returns_result_and_positive_ms():
    result, ms = time_median_ms(lambda: 41 + 1, repeat=2)
    assert result == 42
    assert ms >= 0


def test_flatten_numeric_skips_bools_and_strings():
    flat = flatten_numeric({"a": {"b": 1.5}, "flag": True, "name": "x", "n": 3})
    assert flat == {"a.b": 1.5, "n": 3.0}
