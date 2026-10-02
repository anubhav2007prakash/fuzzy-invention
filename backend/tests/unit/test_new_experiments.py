"""Tests for the new research experiments EXP-F, EXP-G, EXP-H."""
import pytest

from backend.app.services.experiment_service import ExperimentService, KNOWN_EXPERIMENT_IDS


@pytest.fixture(scope="module")
def service():
    return ExperimentService()


def test_registry_contains_robustness_experiment(service):
    assert set(KNOWN_EXPERIMENT_IDS) == {
        "EXP-A", "EXP-B", "EXP-C", "EXP-D", "EXP-F", "EXP-G", "EXP-H",
        "EXP-ROBUSTNESS", "EXP-CALIBRATION",
    }


# ── EXP-F: Component Ablation ────────────────────────────────────────────────

def test_exp_f_runs_all_variants_and_reports_deltas(service):
    res = service.run_exp_f({
        "n_samples": 120,
        "random_state": 42,
        "repeats": 2,
        "explanation_samples": 1,
    })
    assert res["experiment_id"] == "EXP-F"
    assert res["status"] == "COMPLETED"
    variants = res["metrics"]["variants"]
    assert set(variants) == {"A", "B", "C", "D", "E"}
    assert [variants[key]["name"] for key in variants] == [
        "ML only",
        "ML + XAI",
        "ML + cryptographic evidence",
        "ML + XAI + cryptographic evidence",
        "Full SentinelCrypt",
    ]
    for name, data in variants.items():
        for metric in ("precision", "recall", "f1", "f1_macro", "pr_auc"):
            assert 0 <= data["metrics"][metric] <= 1
        assert len(data["runs"]) == 2
        assert data["metric_statistics"]["f1"]["n_trials"] == 2
        assert data["metric_statistics"]["f1"]["raw_data_ref"] == (
            f"/metrics/variants/{name}/runs"
        )
        assert data["metric_statistics"]["f1"]["confidence_interval"] is not None
        assert data["performance"]["inference_latency_ms_per_sample"]["mean"] > 0
        assert data["performance"]["inference_latency_ms_per_sample"]["n"] == 2
        if name in {"B", "D", "E"}:
            assert data["performance"]["explanation_latency_ms_per_sample"]["mean"] > 0
        else:
            assert data["performance"]["explanation_latency_ms_per_sample"]["n"] == 0
            assert data["performance"]["explanation_latency_ms_per_sample"]["mean"] is None
        if name in {"C", "D", "E"}:
            assert data["performance"]["evidence_generation_latency_ms"]["mean"] > 0
            assert data["performance"]["verification_latency_ms"]["mean"] > 0
            assert all(run["evidence_verified"] for run in data["runs"])
        else:
            assert data["performance"]["storage_bytes"]["mean"] == 0
    # Every arm reuses the same fitted model's predictions within a run.
    for run_number in range(2):
        per_arm = [variants[key]["runs"][run_number]["metrics"] for key in variants]
        assert all(metrics == per_arm[0] for metrics in per_arm[1:])
    assert set(res["metrics"]["deltas_vs_A"]) == {"B", "C", "D", "E"}
    assert set(res["metrics"]["deltas_vs_full"]) == {"A", "B", "C", "D"}
    paired_f1 = res["metrics"]["paired_deltas_vs_A"]["E"]["f1"]
    assert paired_f1["n_pairs"] == 2
    assert paired_f1["mean_difference_treatment_minus_baseline"] == 0
    assert paired_f1["p_value"] is None
    assert paired_f1["raw_data_refs"] == [
        "/metrics/variants/A/runs",
        "/metrics/variants/E/runs",
    ]
    assert res["parameters"]["statistical_methodology"]["hypothesis_tests"].startswith("none")
    # ablation results are persisted with a canonical hash
    assert len(res["result_hash"]) == 64


def test_exp_f_rejects_unknown_variant(service):
    with pytest.raises(ValueError, match="Unknown ablation variant"):
        service.run_exp_f({"variants": ["no_such_stage"], "n_samples": 80, "repeats": 1})


def test_exp_f_persists_result_file(service):
    service.run_exp_f({"n_samples": 80, "repeats": 1, "variants": ["A"]})
    from backend.app.services.experiment_service import RESULTS_DIR, EXPERIMENT_RESULT_FILES
    assert (RESULTS_DIR / EXPERIMENT_RESULT_FILES["EXP-F"]).exists()


# ── EXP-G: Hash chain vs Merkle ──────────────────────────────────────────────

def test_exp_g_compares_architectures(service):
    res = service.run_exp_g({"sizes": [64, 256], "random_state": 42})
    assert res["experiment_id"] == "EXP-G"
    assert res["status"] == "COMPLETED"
    for point in res["metrics"]["points"]:
        for arch in ("chain", "merkle"):
            assert point[arch]["verify_ms"] > 0
            assert point[arch]["tamper_mutation_detected"] is True
            assert point[arch]["tamper_omission_detected"] is True
        assert point["verdict"]["both_detect_mutation"] is True
    exponents = res["metrics"]["scaling_exponents"]
    # Both architectures verify full sets in ~O(n), so slope-vs-slope comparison
    # at small sizes is scheduler noise. The structural invariants are: positive
    # bounded slopes, and Merkle's O(log n) inclusion proof beating the chain's
    # per-lookup walk (a >=10x hash-count gap at n>=64, robust to jitter).
    for key in ("chain_verify_time_vs_n", "merkle_verify_time_vs_n"):
        assert 0 < exponents[key] < 2.0
    for point in res["metrics"]["points"]:
        assert point["merkle"]["membership_proof_ms"] < point["chain"]["membership_proof_ms"]
        assert point["verdict"]["cheaper_membership_proof"] == "merkle"


def test_exp_g_persists_result_file(service):
    service.run_exp_g({"sizes": [32]})
    from backend.app.services.experiment_service import RESULTS_DIR, EXPERIMENT_RESULT_FILES
    assert (RESULTS_DIR / EXPERIMENT_RESULT_FILES["EXP-G"]).exists()


# ── EXP-H: XAI agreement ─────────────────────────────────────────────────────

def test_exp_h_measures_agreement_across_noise(service):
    res = service.run_exp_h({"n_samples": 400, "noise_levels": [0.0, 0.1],
                             "n_repetitions_unused": None, "top_k": 5})
    assert res["experiment_id"] == "EXP-H"
    assert res["status"] == "COMPLETED"
    levels = res["metrics"]["agreement_by_noise"]
    assert [l["noise_std"] for l in levels] == [0.0, 0.1]
    clean = res["metrics"]["clean_agreement"]
    assert 0 <= clean["mean_topk_overlap"] <= 1
    assert -1 <= clean["mean_spearman"] <= 1
    assert res["metrics"]["agreement_stable_under_noise"] is not None


def test_exp_h_single_noise_level(service):
    res = service.run_exp_h({"n_samples": 300, "noise_levels": [0.0]})
    assert len(res["metrics"]["agreement_by_noise"]) == 1
    assert res["metrics"]["agreement_stable_under_noise"] is None


def test_exp_h_rejects_negative_noise(service):
    with pytest.raises(ValueError, match="noise_levels must be non-negative"):
        service.run_exp_h({"noise_levels": [-0.1]})


# ── Shared validation ────────────────────────────────────────────────────────

def test_validate_config_accepts_new_experiments(service):
    assert service.validate_experiment_config("EXP-F", {"n_samples": 500})["n_samples"] == 500
    assert service.validate_experiment_config("EXP-G", {"sizes": [10, 20]})["sizes"] == [10, 20]
    assert service.validate_experiment_config("EXP-H", {"top_k": 3})["top_k"] == 3
    config = service.validate_experiment_config(
        "EXP-F", {"repeats": 4, "explanation_samples": 2, "model_type": "logistic_regression"}
    )
    assert config["repeats"] == 4
    assert config["explanation_samples"] == 2
    assert config["model_type"] == "logistic_regression"


def test_validate_config_rejects_bad_values(service):
    with pytest.raises(ValueError):
        service.validate_experiment_config("EXP-F", {"n_samples": 0})
    with pytest.raises(ValueError):
        service.validate_experiment_config("EXP-G", {"sizes": []})
    with pytest.raises(ValueError):
        service.validate_experiment_config("EXP-H", {"top_k": 0})
    with pytest.raises(ValueError, match="at least 40"):
        service.validate_experiment_config("EXP-F", {"n_samples": 20})
    with pytest.raises(ValueError, match="model_type"):
        service.validate_experiment_config("EXP-F", {"model_type": "unsupported"})


def test_unknown_experiment_still_rejected(service):
    with pytest.raises(ValueError, match="Unknown experiment ID"):
        service.validate_experiment_config("EXP-Z", {})
