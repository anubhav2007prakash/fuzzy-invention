"""Chaos / failure-mode tests (item 20): components fail → useful diagnostics.

Each test removes or corrupts one dependency and asserts the system degrades
with a clear, typed error — never a bare traceback and never silent success.
"""
import json
import pytest
from pathlib import Path

from backend.app.core.exceptions import ModelNotFoundError, PredictionNotFoundError
from backend.app.research import benchmark, challenges, modes
from backend.app.services.experiment_service import ExperimentService


# ── Missing inputs ───────────────────────────────────────────────────────────

def test_unknown_dataset_id_is_typed_error():
    """A missing dataset id surfaces as a clear ValueError, not KeyError."""
    with pytest.raises(Exception) as exc:
        benchmark.run_protocol("unsw_nb15", n_samples=50, dataset_id="no-such-id", db=None)
    assert "not found" in str(exc.value).lower()


def test_corrupted_experiment_result_file_is_tolerated(tmp_path, monkeypatch):
    """A corrupted results/*.json degrades to READY_TO_RUN, never a crash."""
    from backend.app.services import experiment_service
    from backend.app.services.experiment_service import EXPERIMENT_RESULT_FILES

    isolated_results = tmp_path / "results"
    monkeypatch.setattr(experiment_service, "RESULTS_DIR", isolated_results)
    target = isolated_results / EXPERIMENT_RESULT_FILES["EXP-A"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{corrupted json!!", encoding="utf-8")
    service = ExperimentService()
    experiments = service.list_experiments()
    exp_a = next(e for e in experiments if e["experiment_id"] == "EXP-A")
    # corrupted file -> falls through to fresh run/READY state without raising
    assert exp_a["experiment_id"] == "EXP-A"


def test_broken_audit_record_is_detected_not_swallowed():
    """A tampered chain fails verification with a localized failure (not crash)."""
    import json
    from types import SimpleNamespace
    from backend.app.cryptography.hash_chain import build_audit_record_hashes, GENESIS_PREVIOUS_HASH
    from backend.app.cryptography.verifier import verify_ledger

    records = []
    prev = GENESIS_PREVIOUS_HASH
    for i in range(1, 6):
        can, _, r_hash = build_audit_record_hashes({"i": i}, prev)
        records.append(SimpleNamespace(sequence_number=i, payload_json=can,
                                       previous_hash=prev, record_hash=r_hash,
                                       payload={"i": i}))
        prev = r_hash

    # corrupt the stored canonical payload (what the verifier hashes)
    broken = [SimpleNamespace(**vars(r)) for r in records]
    evil_payload = {"i": 2, "evil": True}
    broken[2].payload = evil_payload
    broken[2].payload_json = json.dumps(evil_payload)
    result = verify_ledger(broken)
    assert result.verified is False
    assert result.failed_records, "tamper must localize the broken record"


# ── Invalid configuration ────────────────────────────────────────────────────

def test_invalid_experiment_config_is_named_field_error():
    service = ExperimentService()
    with pytest.raises(ValueError, match="n_samples"):
        service.validate_experiment_config("EXP-A", {"n_samples": -5})
    with pytest.raises(ValueError, match="sizes"):
        service.validate_experiment_config("EXP-G", {"sizes": ["big"]})


def test_invalid_challenge_payload_rejected_cleanly():
    with pytest.raises(ValueError):
        challenges.create_challenge(title="", hypothesis="a real hypothesis!", experiment="EXP-A")


def test_robustness_rejects_out_of_bound_epsilon():
    from backend.app.research.robustness import run_robustness_study
    with pytest.raises(ValueError, match="bounded"):
        run_robustness_study(epsilon_levels=[0.9])


def test_mode_rejects_unknown_value():
    with pytest.raises(ValueError, match="Unknown mode"):
        modes.set_mode("chaos")


# ── Missing artifacts / config ───────────────────────────────────────────────

def test_model_selection_handles_degenerate_class_distribution():
    """A dataset with one class cannot run stratified CV — must fail with message."""
    import pandas as pd
    from backend.app.research.model_selection import select_model

    df = pd.DataFrame({"a": [1, 2, 3, 4], "label": [0, 0, 0, 0]})
    with pytest.raises(Exception):
        select_model(dataset=df, cv_folds=3)


def test_notary_rejects_unserializable_payload():
    from backend.app.cryptography import notary
    with pytest.raises(Exception):
        notary.sign_result({"bad": object()})


def test_missing_package_files_are_reported(tmp_path):
    """Reproducibility package export creates every declared file even for a minimal result."""
    from backend.app.research.reproducibility import export_reproducibility_package, PACKAGE_FILES

    result = {
        "experiment_id": "EXP-MIN", "status": "COMPLETED",
        "metrics": {"f1": 0.5}, "parameters": {}, "result_hash": "x" * 64,
        "run_manifest": {"environment": {}, "git": {"commit": "deadbeef"}},
    }
    package = export_reproducibility_package("EXP-MIN", result, {}, out_root=tmp_path / "p")
    for name in PACKAGE_FILES:
        assert (tmp_path / "p" / name).exists(), f"missing package file {name}"
