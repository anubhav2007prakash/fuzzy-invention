"""Tests for cross-validated model selection."""
import numpy as np
import pytest

from backend.app.ml.data.synthetic import generate_flow_dataset
from backend.app.research.model_selection import CANDIDATES, analyze_dataset, select_model


def test_candidates_registry_has_five_models():
    assert set(CANDIDATES) == {
        "logistic_regression", "random_forest", "gaussian_nb",
        "gradient_boosting", "svm_rbf",
    }


def test_analyze_dataset_reports_imbalance():
    df = generate_flow_dataset(n_samples=300, random_state=42, attack_ratio=0.3)
    analysis = analyze_dataset(df)
    assert analysis["n_samples"] == 300
    assert analysis["class_distribution"] == {"0": 210, "1": 90}
    assert 0 < analysis["imbalance_ratio"] <= 1
    assert analysis["high_imbalance"] is False


def test_select_model_ranks_all_candidates():
    result = select_model(n_samples=400, cv_folds=3, seed=42)
    assert result["status"] == "COMPLETED"
    evaluated = [r for r in result["candidates"] if r["status"] == "evaluated"]
    assert len(evaluated) == 5
    for row in evaluated:
        assert 0 <= row["f1_macro"] <= 1
        assert "roc_auc" in row and "fit_time_ms_mean" in row
    # winner is measured, not hard-coded
    assert result["selected_model"] == result["ranking"][0]
    assert result["selection_margin_f1_macro"] is not None


def test_select_model_with_subset_of_candidates():
    result = select_model(candidates=["random_forest", "gaussian_nb"],
                          n_samples=300, cv_folds=3)
    assert [r["model"] for r in result["candidates"]] == ["random_forest", "gaussian_nb"]
    assert result["selected_model"] in ("random_forest", "gaussian_nb")


def test_select_model_unknown_candidate_rejected():
    with pytest.raises(ValueError, match="Unknown candidate"):
        select_model(candidates=["transformer_xl"])


def test_select_model_bad_target_column():
    df = generate_flow_dataset(n_samples=100)
    with pytest.raises(ValueError, match="Target column"):
        select_model(dataset=df, target_column="attack_flag")


def test_selection_is_measured_not_hardcoded():
    # The winner must be the top-ranked CV row (name tie-break on equal scores),
    # never a constant.
    result_a = select_model(n_samples=350, cv_folds=3, seed=7)
    result_b = select_model(n_samples=350, cv_folds=3, seed=7)
    assert result_a["selected_model"] == result_b["selected_model"]  # deterministic
    assert result_a["selected_model"] == result_a["ranking"][0]
    best_f1 = max(
        (r.get("f1_macro") or -1) for r in result_a["candidates"]
        if r.get("status") == "evaluated"
    )
    winner_row = next(
        r for r in result_a["candidates"] if r["model"] == result_a["selected_model"]
    )
    assert winner_row["f1_macro"] >= best_f1 - 1e-9
