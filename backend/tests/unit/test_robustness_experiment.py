"""Behavioral tests for the registered EXP-ROBUSTNESS experiment."""
import pytest

from backend.app.services.experiment_service import ExperimentService


@pytest.fixture(scope="module")
def service():
    return ExperimentService()


def test_robustness_experiment_reports_stability_confidence_and_metric_changes(service):
    result = service.run_exp_robustness({
        "n_samples": 160,
        "n_probe": 8,
        "epsilon_levels": [0.02, 0.08],
        "random_state": 17,
        "n_repeats": 2,
        "with_explanations": False,
    })

    assert result["experiment_id"] == "EXP-ROBUSTNESS"
    assert result["status"] == "COMPLETED"
    assert result["parameters"]["data_source"] == "controlled_synthetic_fixture"
    assert result["parameters"]["explanations_measured"] is False
    assert "no robustness claim" in result["interpretation"].lower()
    assert [point["epsilon"] for point in result["metrics"]["conditions"]] == [
        0.02, 0.08,
    ]

    for condition in result["metrics"]["conditions"]:
        assert condition["prediction_stability"]["mean"] is not None
        assert condition["confidence_change"]["mean"] is not None
        assert condition["prediction_stability"]["n_trials"] == 2
        assert len(condition["trials"]) == 2
        assert condition["maximum_perturbation_fraction_of_train_range"] <= (
            condition["epsilon"] + 1e-12
        )
        assert set(condition["metric_changes"]) >= {
            "accuracy", "precision", "recall", "f1", "f1_macro", "pr_auc",
        }
        assert condition["metric_changes"]["f1"]["n_trials"] == 2
        assert condition["explanation_stability"]["mean"] is None

    assert len(result["result_hash"]) == 64


def test_robustness_experiment_rejects_unbounded_or_duplicate_conditions(service):
    with pytest.raises(ValueError, match="maximum"):
        service.run_exp_robustness({
            "epsilon_levels": [0.21],
            "with_explanations": False,
        })
    with pytest.raises(ValueError, match="unique"):
        service.run_exp_robustness({
            "epsilon_levels": [0.05, 0.05],
            "with_explanations": False,
        })


def test_robustness_experiment_rejects_invalid_probe_and_model(service):
    with pytest.raises(ValueError, match="n_probe"):
        service.validate_experiment_config("EXP-ROBUSTNESS", {"n_probe": 0})
    with pytest.raises(ValueError, match="model_type"):
        service.validate_experiment_config(
            "EXP-ROBUSTNESS", {"model_type": "unsupported"}
        )


def test_robustness_experiment_is_reproducible_for_fixed_seed(service):
    config = {
        "n_samples": 120,
        "n_probe": 6,
        "epsilon_levels": [0.04],
        "random_state": 91,
        "n_repeats": 2,
        "with_explanations": False,
    }
    first = service.run_exp_robustness(config)
    second = service.run_exp_robustness(config)

    assert first["result_hash"] == second["result_hash"]
    assert first["metrics"]["conditions"][0]["trials"] == (
        second["metrics"]["conditions"][0]["trials"]
    )
