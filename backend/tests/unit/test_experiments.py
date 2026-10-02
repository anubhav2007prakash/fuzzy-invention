"""Unit tests for SentinelCrypt Research Experiments (EXP-A to EXP-D)."""
import json
from pathlib import Path
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
    # Verify synthetic data is clearly labeled (not claiming real UNSW/CICIDS)
    assert "Synthetic" in res["title"]

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
    ids = {e["experiment_id"] for e in experiments}
    assert {
        "EXP-A", "EXP-B", "EXP-C", "EXP-D", "EXP-F", "EXP-G", "EXP-H",
        "EXP-ROBUSTNESS", "EXP-CALIBRATION",
    } == ids
    assert len(experiments) == 9

    exp_a = service.get_experiment_by_id("EXP-A")
    assert exp_a is not None
    assert exp_a["experiment_id"] == "EXP-A"

def test_research_envelope_is_added_to_experiment_result(service):
    res = service.run_exp_a({"n_samples": 300, "random_state": 42})

    assert res["experiment_id"] == "EXP-A"
    assert res["status"] == "COMPLETED"
    assert len(res["result_hash"]) == 64
    assert len(res["configuration_hash"]) == 64
    assert res["run_manifest"]["experiment_id"] == "EXP-A"
    assert res["run_manifest"]["configuration"]["n_samples"] == 300
    assert res["run_manifest"]["configuration"]["random_state"] == 42
    assert res["run_manifest"]["dataset_scope"] == "synthetic"
    assert res["evidence_package"]["status"] == "not_exported"
    assert {d["label"] for d in res["trust_profile"]} == {
        "Detection",
        "Explanation Stability",
        "Evidence Integrity",
        "Reproducibility",
        "Data Quality",
    }

def test_hash_helpers_are_deterministic_for_same_payload(service):
    payload = {
        "experiment_id": "EXP-Z",
        "status": "COMPLETED",
        "metrics": {"f1_score": 0.9123456},
        "timestamp": "2026-09-21T00:00:00Z",
    }
    config = {"n_samples": 300, "random_state": 42}

    assert service.calculate_result_hash(payload) == service.calculate_result_hash(dict(payload))
    assert service.calculate_configuration_hash("EXP-Z", config) == service.calculate_configuration_hash("exp-z", dict(config))

def test_validate_experiment_config_rejects_invalid_values(service):
    with pytest.raises(ValueError, match="n_samples"):
        service.validate_experiment_config("EXP-A", {"n_samples": 0, "random_state": 42})

    with pytest.raises(ValueError, match="noise_levels"):
        service.validate_experiment_config("EXP-B", {"noise_levels": [-0.1], "n_repetitions": 3, "random_state": 42})

    with pytest.raises(ValueError, match="n_blocks"):
        service.validate_experiment_config("EXP-C", {"n_blocks": "many", "random_state": 42})

def test_data_quality_trust_dimension_is_not_evaluated_without_real_dataset(service):
    res = service.run_exp_d({"n_samples": 400, "random_state": 42})
    data_quality = next(d for d in res["trust_profile"] if d["label"] == "Data Quality")

    assert data_quality["status"] == "not_evaluated"
    assert data_quality["value"] is None
    assert "No real dataset health report" in data_quality["explanation"]

def test_export_evidence_package_writes_expected_files(service):
    service.run_exp_c({"n_blocks": 12, "random_state": 42})

    package = service.export_evidence_package("EXP-C")

    assert package["experiment_id"] == "EXP-C"
    assert package["evidence_format_version"] == 2
    assert package["protocol_version"] == 1
    assert package["schema_version"] == 1
    assert package["experiment_schema_version"] == 1
    assert package["research_artifact_version"] == 1
    assert package["package_hash"]
    assert len(package["package_hash"]) == 64
    assert package["package_path"].endswith("results/evidence/EXP-C")
    assert set(package["files"]) == {
        "package-manifest.json",
        "README.md",
        "experiment.json",
        "metrics.json",
        "reproducibility-manifest.json",
        "verification-report.json",
    }

    package_dir = Path(package["package_path"])
    assert (package_dir / "experiment.json").exists()
    assert (package_dir / "metrics.json").exists()
    assert (package_dir / "reproducibility-manifest.json").exists()
    assert (package_dir / "verification-report.json").exists()
    version_manifest = json.loads(
        (package_dir / "package-manifest.json").read_text(encoding="utf-8")
    )
    assert version_manifest["evidence_format_version"] == 2
    assert version_manifest["protocol_version"] == 1
    assert version_manifest["schema_version"] == 1
    assert version_manifest["experiment_schema_version"] == 1
    assert version_manifest["research_artifact_version"] == 1
    assert (package_dir / "verification-report.json").exists()
    assert (package_dir / "README.md").exists()

def test_presentation_summary_contains_research_narrative_and_limitations(service):
    summary = service.build_presentation_summary()

    assert summary["research_question"].startswith("How does explanation reliability")
    assert "Random Forest" in summary["models"]
    assert "SHAP" in summary["xai_method"]
    assert "SHA-256" in summary["cryptographic_evidence"]
    assert len(summary["experiments"]) == 8
    assert "Current experiments use synthetic data." in summary["limitations"]
    assert "research prototype" in " ".join(summary["limitations"]).lower()
