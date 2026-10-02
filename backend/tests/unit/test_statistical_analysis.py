"""Design-aware statistical summaries and raw-observation provenance."""
import hashlib

import pytest

from backend.app.cryptography.canonicalization import canonicalize
from backend.app.ml.evaluation.statistical_analysis import (
    bootstrap_trial_summary,
    descriptive_observation_summary,
    independent_bootstrap_comparison,
    paired_bootstrap_comparison,
)


def test_bootstrap_summary_is_repeatable_and_references_raw_values():
    summary = bootstrap_trial_summary(
        [0.7, 0.8, 0.9],
        ["seed-1", "seed-2", "seed-3"],
        raw_data_ref="/trials",
        bootstrap_resamples=500,
        seed=7,
    )

    observations = summary["raw_observations"]
    assert summary["raw_data_ref"] == "/trials"
    assert summary["raw_data_sha256"] == hashlib.sha256(
        canonicalize(observations).encode("utf-8")
    ).hexdigest()
    assert summary["n_trials"] == 3
    assert summary["sample_variance"] == pytest.approx(0.01)
    assert summary["confidence_interval"]["low"] <= summary["mean"]
    assert summary["confidence_interval"]["high"] >= summary["mean"]
    second = bootstrap_trial_summary(
        [0.7, 0.8, 0.9],
        ["seed-1", "seed-2", "seed-3"],
        raw_data_ref="/trials",
        bootstrap_resamples=500,
        seed=7,
    )
    assert second["confidence_interval"] == summary["confidence_interval"]


def test_single_trial_does_not_invent_variance_or_confidence_interval():
    summary = bootstrap_trial_summary(
        [0.75],
        ["seed-1"],
        raw_data_ref="/trials",
        bootstrap_resamples=500,
    )
    assert summary["sample_variance"] is None
    assert summary["sample_std"] is None
    assert summary["confidence_interval"] is None


def test_condition_series_is_descriptive_and_references_condition_observations():
    summary = descriptive_observation_summary(
        [0.8, 0.6],
        ["noise-0", "noise-1"],
        raw_data_ref="/metrics/agreement_by_noise/*/score",
        design="two configured conditions",
        observation_type="condition",
    )
    assert summary["n_conditions"] == 2
    assert summary["confidence_interval"] is None
    assert summary["raw_observations"] == [
        {"condition_id": "noise-0", "value": 0.8},
        {"condition_id": "noise-1", "value": 0.6},
    ]
    assert len(summary["raw_data_sha256"]) == 64


def test_paired_bootstrap_requires_matching_trial_ids_and_reports_dz():
    result = paired_bootstrap_comparison(
        [0.70, 0.75, 0.80],
        [0.75, 0.82, 0.85],
        ["seed-1", "seed-2", "seed-3"],
        ["seed-1", "seed-2", "seed-3"],
        baseline_raw_data_ref="/arms/A/runs",
        treatment_raw_data_ref="/arms/B/runs",
        bootstrap_resamples=500,
        seed=9,
    )
    assert result["design"] == "paired repeated trials"
    assert result["mean_difference_treatment_minus_baseline"] > 0
    assert result["cohens_dz"] > 0
    assert result["p_value"] is None
    assert result["significance_claim"] is None
    assert result["raw_data_refs"] == ["/arms/A/runs", "/arms/B/runs"]
    assert len(result["raw_data_sha256"]) == 64

    with pytest.raises(ValueError, match="matching ordered trial_ids"):
        paired_bootstrap_comparison(
            [0.70, 0.75],
            [0.75, 0.82],
            ["seed-1", "seed-2"],
            ["seed-2", "seed-1"],
            baseline_raw_data_ref="/arms/A/runs",
            treatment_raw_data_ref="/arms/B/runs",
            bootstrap_resamples=500,
        )


def test_independent_bootstrap_resamples_groups_without_significance_claim():
    result = independent_bootstrap_comparison(
        [0.60, 0.65, 0.70],
        [0.75, 0.80, 0.82],
        ["baseline-1", "baseline-2", "baseline-3"],
        ["alternative-1", "alternative-2", "alternative-3"],
        baseline_raw_data_ref="/raw/baseline",
        treatment_raw_data_ref="/raw/alternative",
        bootstrap_resamples=500,
        seed=11,
    )
    assert result["design"] == "independent repeated trials"
    assert result["mean_difference_treatment_minus_baseline"] > 0
    assert result["confidence_interval"]["low"] > 0
    assert result["p_value"] is None
    assert result["significance_claim"] is None
    assert len(result["raw_data_sha256"]) == 64


def test_independent_bootstrap_requires_two_trials_for_interval_and_effect_size():
    result = independent_bootstrap_comparison(
        [0.6],
        [0.8, 0.9],
        ["baseline-1"],
        ["alternative-1", "alternative-2"],
        baseline_raw_data_ref="/raw/baseline",
        treatment_raw_data_ref="/raw/alternative",
        bootstrap_resamples=500,
    )
    assert result["confidence_interval"] is None
    assert result["cohens_d"] is None
    assert result["baseline_sample_variance"] is None
    assert result["treatment_sample_variance"] is not None


@pytest.mark.parametrize(
    ("values", "trial_ids"),
    [
        ([1.0, 2.0], ["only-one"]),
        ([float("nan")], ["nan"]),
        ([1.0, 2.0], ["same", "same"]),
    ],
)
def test_bootstrap_summary_rejects_invalid_raw_trials(values, trial_ids):
    with pytest.raises(ValueError):
        bootstrap_trial_summary(
            values,
            trial_ids,
            raw_data_ref="/trials",
            bootstrap_resamples=500,
        )
