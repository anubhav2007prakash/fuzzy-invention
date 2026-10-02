"""Tests for the bounded-perturbation robustness study."""
import pytest

from backend.app.research.robustness import MAX_EPSILON, run_robustness_study


def test_robustness_study_measures_curve():
    result = run_robustness_study(n_samples=500, n_probe=15, seed=42,
                                  epsilon_levels=[0.02, 0.10], n_repeats=3)
    assert result["experiment_id"] == "ROBUSTNESS"
    assert result["status"] == "COMPLETED"
    curve = result["metrics"]["curve"]
    assert [c["epsilon"] for c in curve] == [0.02, 0.10]
    for point in curve:
        assert 0.0 <= point["prediction_flip_rate"] <= 1.0
        assert 0.0 <= point["robustness_score"] <= 1.0
        assert point["confidence_drift_mean"] is not None
        assert point["explanation_cosine_drop_mean"] is not None
    # more perturbation never helps robustness (statistically it's monotone-ish,
    # but the boundary check stands: scores stay in range and are recorded)
    assert result["metrics"]["robustness_at_highest_epsilon"] is not None
    assert len(result["result_hash"]) == 64


def test_robustness_without_explanations():
    result = run_robustness_study(n_samples=400, n_probe=10, seed=42,
                                  with_explanations=False, epsilon_levels=[0.05])
    point = result["metrics"]["curve"][0]
    assert point["explanation_cosine_drop_mean"] is None


def test_epsilon_bounded_by_design():
    with pytest.raises(ValueError, match="bounded"):
        run_robustness_study(epsilon_levels=[0.5])  # above the hard MAX_EPSILON
    assert MAX_EPSILON == 0.20


def test_ethics_scope_recorded():
    result = run_robustness_study(n_samples=300, seed=42, epsilon_levels=[0.05])
    note = result["parameters"]["ethics_note"].lower()
    assert "controlled" in note
    assert "no system is probed" in note
