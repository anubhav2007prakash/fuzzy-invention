"""Unit tests for SentinelCrypt Research Experiments (EXP-A to EXP-D)."""
import pytest
from backend.app.services.experiment_service import ExperimentService

@pytest.fixture
def service():
    return ExperimentService()

def test_exp_a_execution(service):
    res = service.run_exp_a({"n_samples": 400, "random_state": 42})
    assert res["experiment_id"] == "EXP-A"
    assert res["status"] == "COMPLETED"
    assert "in_distribution" in res["metrics"]
    assert "out_of_distribution" in res["metrics"]
    assert "generalization_gap" in res["metrics"]
    assert 0.0 <= res["metrics"]["in_distribution"]["f1_score"] <= 1.0

def test_exp_b_execution(service):
    res = service.run_exp_b({"noise_levels": [0.01, 0.05], "n_repetitions": 3, "random_state": 42})
    assert res["experiment_id"] == "EXP-B"
    assert res["status"] == "COMPLETED"
    assert "stability_curve" in res["metrics"]
    assert len(res["metrics"]["stability_curve"]) == 2
    assert 0.0 <= res["metrics"]["overall_mean_stability"] <= 1.0

def test_exp_c_execution(service):
    res = service.run_exp_c({"n_blocks": 25, "random_state": 42})
    assert res["experiment_id"] == "EXP-C"
    assert res["status"] == "COMPLETED"
    assert res["metrics"]["clean_chain_valid"] is True
    assert res["metrics"]["tamper_detection_rate"] == "100.0%"
    assert len(res["metrics"]["attacks_simulated"]) == 3
    for attack in res["metrics"]["attacks_simulated"]:
        assert attack["detected"] is True
        assert attack["status"] == "PASSED"

def test_exp_d_execution(service):
    res = service.run_exp_d({"n_samples": 500, "random_state": 42})
    assert res["experiment_id"] == "EXP-D"
    assert res["status"] == "COMPLETED"
    assert "logistic_regression" in res["comparison"]
    assert "random_forest" in res["comparison"]
    assert "cryptographic_overhead" in res["comparison"]
    assert res["comparison"]["logistic_regression"]["f1_score"] >= 0.0
    assert res["comparison"]["random_forest"]["f1_score"] >= 0.0

def test_list_and_get_experiments(service):
    experiments = service.list_experiments()
    assert len(experiments) == 4
    ids = {e["experiment_id"] for e in experiments}
    assert ids == {"EXP-A", "EXP-B", "EXP-C", "EXP-D"}

    exp_a = service.get_experiment_by_id("EXP-A")
    assert exp_a is not None
    assert exp_a["experiment_id"] == "EXP-A"
