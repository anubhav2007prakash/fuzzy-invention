"""Tests for the research challenge framework."""
import json

import pytest

from backend.app.research import challenges


def test_define_challenge_validates_input():
    challenge = challenges.create_challenge(
        title="Stability under noise",
        hypothesis="SHAP attributions stay above 0.8 cosine under sigma=0.05 noise.",
        experiment="EXP-B",
        kind="standard",
        config={"n_repetitions": 3, "noise_levels": [0.05], "random_state": 42},
    )
    assert challenge["status"] == "DEFINED"
    assert challenge["challenge_id"].startswith("CH-")
    assert challenge["seed"] == 42


def test_define_rejects_bad_hypothesis_and_kind():
    with pytest.raises(ValueError, match="title"):
        challenges.create_challenge(title="", hypothesis="x is correlated with y!", experiment="EXP-A")
    with pytest.raises(ValueError, match="Hypothesis"):
        challenges.create_challenge(title="T", hypothesis="short", experiment="EXP-A")
    with pytest.raises(ValueError, match="kind"):
        challenges.create_challenge(title="T", hypothesis="a meaningful hypothesis!", experiment="EXP-A", kind="magic")
    with pytest.raises(ValueError, match="experiment"):
        challenges.create_challenge(title="T", hypothesis="a meaningful hypothesis!", experiment="")


def test_standard_challenge_runs_with_statistics():
    challenge = challenges.create_challenge(
        title="EXP-D runtime variation",
        hypothesis="EXP-D completes with stable macro-F1 across repeated runs.",
        experiment="EXP-D",
        config={"n_samples": 300, "random_state": 42},
    )
    result = challenges.run_challenge(challenge, n_runs=3)
    assert result["status"] == "COMPLETED"
    assert result["analysis"]["runs"] == 3
    assert result["analysis"]["metric_stats"], "expected at least one metric series"
    assert result["analysis"]["runtime_ms"]["n"] == 3
    metric_summary = next(iter(result["analysis"]["metric_stats"].values()))
    assert metric_summary["confidence_interval"] is None
    assert metric_summary["raw_data_ref"].startswith("/runs/")
    assert len(metric_summary["raw_data_sha256"]) == 64
    assert result["analysis"]["statistical_methodology"]["hypothesis_tests"] == "none"
    assert len(result["evidence_hash"]) == 64
    assert result["persisted_to"]


def test_longitudinal_challenge_tracks_drift():
    challenge = challenges.create_challenge(
        title="Longitudinal EXP-A",
        hypothesis="Metric variation across repeated runs stays within one point of F1.",
        experiment="EXP-A",
        kind="longitudinal",
        config={"n_samples": 300, "vary_seed": True, "random_state": 42},
    )
    result = challenges.run_challenge(challenge, n_runs=4)
    assert result["kind"] == "longitudinal"
    assert "drift_slope_per_run" in result["analysis"]
    metric_summary = next(iter(result["analysis"]["metric_stats"].values()))
    assert metric_summary["method"].startswith("trial-level percentile bootstrap")
    assert metric_summary["confidence_interval"] is not None
    assert metric_summary["n_trials"] == 4


def test_reproducibility_challenge_classifies_determinism():
    challenge = challenges.create_challenge(
        title="Same config rerun determinism",
        hypothesis="Identical configuration reproduces identical canonical hashes.",
        experiment="EXP-A",
        kind="reproducibility",
        config={"n_samples": 300, "random_state": 42},
    )
    result = challenges.run_challenge(challenge, n_runs=3)
    analysis = result["analysis"]
    assert analysis["runs"] == 3
    assert analysis["hash_identical_across_runs"] is True
    assert analysis["determinism_classification"].startswith("fully_deterministic")
    metric_summary = next(iter(analysis["metric_stats"].values()))
    assert metric_summary["confidence_interval"] is None
    assert metric_summary["design"].startswith("identical-configuration")


def test_preset_run_q5_reproducibility():
    result = challenges.run_preset("Q5", n_runs=2)
    assert result["question_id"] == "Q5"
    assert result["kind"] == "reproducibility"
    assert result["analysis"]["hash_identical_across_runs"] is True


def test_all_presets_defined_and_runnable_shape():
    ids = [p["id"] for p in challenges.QUESTION_PRESETS]
    assert ids == ["Q1", "Q2", "Q3", "Q4", "Q5"]
    for preset in challenges.QUESTION_PRESETS:
        assert preset["question"] and preset["hypothesis"]
        assert preset["kind"] in challenges.KINDS
        assert preset["experiment"]


def test_unknown_preset_rejected():
    with pytest.raises(ValueError, match="Unknown question preset"):
        challenges.run_preset("Q99")


def test_challenge_persistence_round_trip():
    challenge = challenges.create_challenge(
        title="Persistence probe",
        hypothesis="Persisted challenges are retrievable from results/challenges.",
        experiment="EXP-D",
        config={"n_samples": 250, "random_state": 42},
    )
    result = challenges.run_challenge(challenge, n_runs=1)
    fetched = challenges.get_challenge(result["challenge_id"])
    assert fetched["challenge_id"] == result["challenge_id"]
    assert fetched["analysis"]["runs"] == 1
    listing = challenges.list_challenges()
    assert any(c["challenge_id"] == result["challenge_id"] for c in listing)


def test_benchmark_challenge_via_presets_q3():
    result = challenges.run_preset("Q3", n_runs=1)
    assert result["experiment"] == "BENCHMARK"
    assert result["status"] == "COMPLETED"
