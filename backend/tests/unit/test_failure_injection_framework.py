"""Unit tests for the failure injection framework itself.

Verifies that injectors cleanly activate, inject faults, and safely revert,
and that invariant assertion helpers behave correctly.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import OperationalError

from backend.app.core.config import settings
from backend.app.core.exceptions import (
    ModelNotFoundError,
    PredictionFailedError,
    SentinelCryptException,
)
from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    calculate_payload_hash,
    calculate_record_hash,
)
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.db.models import Base, AuditRecord, ModelRecord, Prediction
from backend.tests.failure_injection import (
    BaseFaultInjector,
    DatabaseUnavailableInjector,
    MissingModelArtifactInjector,
    CorruptedDatasetInjector,
    CorruptedAuditRecordInjector,
    SHAPFailureInjector,
    IncompleteExperimentInjector,
    MissingConfigurationInjector,
    UnavailableDependencyInjector,
    InvalidAPIInputInjector,
    FailureVerificationRecord,
    FailureVerificationReport,
    assert_consistent_state,
    assert_evidence_not_corrupted,
    assert_fails_safely,
    assert_meaningful_error,
    assert_no_silent_invalid_results,
    inject_database_unavailable,
    inject_missing_model_artifact,
    inject_dataset_corruption,
    inject_audit_corruption,
    inject_shap_failure,
    inject_incomplete_experiment,
    inject_missing_configuration,
    inject_unavailable_dependency,
)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


# ── Test DatabaseUnavailableInjector ──────────────────────────────────────────

def test_database_unavailable_injector_lifecycle(db_session):
    # Before injection: query works
    res = db_session.execute(Base.metadata.tables["models"].select()).fetchall()
    assert res == []

    # Inside injection: raises OperationalError
    with inject_database_unavailable(db_session=db_session, error_message="DB down"):
        with pytest.raises(OperationalError) as exc_info:
            db_session.execute(Base.metadata.tables["models"].select())
        assert "DB down" in str(exc_info.value)

    # After injection: query works again cleanly
    res_after = db_session.execute(Base.metadata.tables["models"].select()).fetchall()
    assert res_after == []


# ── Test MissingModelArtifactInjector ─────────────────────────────────────────

def test_missing_model_artifact_injector_lifecycle():
    from backend.app.ml.registry import ModelRegistry
    from unittest.mock import patch

    with patch.object(
        ModelRegistry, "load_model", staticmethod(lambda path: ("restored", path))
    ):
        with inject_missing_model_artifact(artifact_path="fake/path.joblib"):
            with pytest.raises(FileNotFoundError) as exc_info:
                ModelRegistry.load_model("fake/path.joblib")
            assert "fake/path.joblib" in str(exc_info.value)

        assert ModelRegistry.load_model("after-injection") == (
            "restored",
            "after-injection",
        )


def test_fault_injector_cleans_up_partial_activation():
    class PartiallyActivatingInjector(BaseFaultInjector):
        def __init__(self):
            super().__init__("partial")
            self.changed = False

        def activate(self):
            self.changed = True
            raise RuntimeError("activation failed")

        def deactivate(self):
            self.changed = False

    injector = PartiallyActivatingInjector()
    with pytest.raises(RuntimeError, match="activation failed"):
        with injector:
            pytest.fail("activation should not complete")

    assert injector.changed is False
    assert injector.is_active is False


def test_fault_injector_rejects_reentrant_activation():
    injector = inject_missing_configuration({"PROJECT_NAME": "TEMPORARY_CHAOS"})
    with injector:
        with pytest.raises(RuntimeError, match="already active"):
            injector.__enter__()


def test_invalid_fault_specifications_fail_instead_of_noop():
    with pytest.raises(ValueError, match="Unsupported audit corruption"):
        with CorruptedAuditRecordInjector([], attack_type="unknown"):
            pass

    with pytest.raises(ValueError, match="out of range"):
        with CorruptedAuditRecordInjector([], target_index=0):
            pass

    with pytest.raises(ValueError, match="Unsupported experiment"):
        IncompleteExperimentInjector("EXP-UNKNOWN")

    with pytest.raises(ValueError, match="Unknown SentinelCrypt setting"):
        with inject_missing_configuration({"NOT_A_REAL_SETTING": "value"}):
            pass


def test_invariant_helpers_reject_success_shaped_outcomes():
    with pytest.raises(AssertionError, match="succeeded unexpectedly"):
        assert_fails_safely(lambda: {"status": "COMPLETED"})

    with pytest.raises(AssertionError, match="silently succeeded"):
        assert_no_silent_invalid_results({"status": "COMPLETED"})

    with pytest.raises(AssertionError, match="does not explicitly report failure"):
        assert_no_silent_invalid_results({"metrics": {"f1": 1.0}})


def test_failure_assertions_accept_structured_http_errors():
    response = SimpleNamespace(
        status_code=503,
        json=lambda: {"error": {"code": "DATABASE_UNAVAILABLE", "message": "offline"}},
    )
    assert_fails_safely(response)
    assert_no_silent_invalid_results(response)

    invalid = SimpleNamespace(status_code=200, json=lambda: {"status": "COMPLETED"})
    with pytest.raises(AssertionError, match="successful HTTP status"):
        assert_fails_safely(invalid)


def _valid_records(count=2):
    records = []
    previous_hash = GENESIS_PREVIOUS_HASH
    for sequence_number in range(1, count + 1):
        payload = {"sequence_number": sequence_number}
        payload_json = canonicalize(payload)
        payload_digest = calculate_payload_hash(payload)
        record_digest = calculate_record_hash(previous_hash, payload_digest)
        records.append(SimpleNamespace(
            sequence_number=sequence_number,
            payload_json=payload_json,
            previous_hash=previous_hash,
            record_hash=record_digest,
        ))
        previous_hash = record_digest
    return records


def test_evidence_assertion_detects_deletion_duplicate_and_corruption():
    records = _valid_records()
    with pytest.raises(AssertionError, match="was deleted"):
        assert_evidence_not_corrupted(records, records[:1])

    with pytest.raises(AssertionError, match="duplicate sequence"):
        assert_evidence_not_corrupted(records, records + [records[0]])

    corrupted = [SimpleNamespace(**vars(record)) for record in records]
    corrupted[1].payload_json = '{"sequence_number":999}'
    with pytest.raises(AssertionError, match="was corrupted"):
        assert_evidence_not_corrupted(records, corrupted)


def test_evidence_assertion_checks_post_failure_chain():
    records = _valid_records()
    post_failure = [SimpleNamespace(**vars(record)) for record in records]
    post_failure.append(SimpleNamespace(
        sequence_number=3,
        payload_json='{"sequence_number":3}',
        previous_hash=post_failure[-1].record_hash,
        record_hash="f" * 64,
    ))
    with pytest.raises(AssertionError, match="Post-failure ledger failed verification"):
        assert_evidence_not_corrupted(records, post_failure)


def test_expected_entity_count_requires_a_known_integrity_key(db_session):
    with pytest.raises(AssertionError, match="Unknown entity count key"):
        assert_consistent_state(db_session, {"not_a_table": 0})


# ── Test CorruptedDatasetInjector ─────────────────────────────────────────────

def test_corrupted_dataset_injector_generates_samples():
    raw_syntax_error = CorruptedDatasetInjector.generate_corrupted_csv("syntax_error")
    assert b"unclosed_string_field" in raw_syntax_error

    raw_empty = CorruptedDatasetInjector.generate_corrupted_csv("empty")
    assert raw_empty == b""

    raw_truncated = CorruptedDatasetInjector.generate_corrupted_csv("truncated")
    assert b"dur,proto" in raw_truncated


def test_corrupted_dataset_injector_disk_tamper(tmp_path):
    target = tmp_path / "dataset.csv"
    orig_content = b"feature1,feature2,label\n1.0,2.0,0\n"
    target.write_bytes(orig_content)

    with inject_dataset_corruption(file_path=target, corruption_type="tampered_bytes"):
        tampered_content = target.read_bytes()
        assert tampered_content != orig_content
        assert b"TAMPERED_ROW" in tampered_content

    # Clean reversion
    assert target.read_bytes() == orig_content


def test_dataset_corruption_rejects_non_temporary_and_missing_files(tmp_path):
    repository_file = Path(__file__).resolve()
    with pytest.raises(ValueError, match="restricted to files under"):
        with inject_dataset_corruption(file_path=repository_file):
            pass

    missing_fixture = tmp_path / "missing.csv"
    with pytest.raises(FileNotFoundError, match="test fixture does not exist"):
        with inject_dataset_corruption(file_path=missing_fixture):
            pass

    with pytest.raises(ValueError, match="Unsupported dataset corruption type"):
        with inject_dataset_corruption(
            file_path=tmp_path / "existing.csv",
            corruption_type="not-a-real-mode",
        ):
            pass


# ── Test CorruptedAuditRecordInjector ─────────────────────────────────────────

def test_corrupted_audit_record_injector_reverts_state():
    records = []
    prev = GENESIS_PREVIOUS_HASH
    for i in range(1, 4):
        payload = {"seq": i, "val": 100 * i}
        pj = canonicalize(payload)
        ph = calculate_payload_hash(payload)
        rh = calculate_record_hash(prev, ph)
        records.append(SimpleNamespace(
            sequence_number=i,
            payload_json=pj,
            previous_hash=prev,
            record_hash=rh,
            payload=payload,
        ))
        prev = rh

    orig_json = records[1].payload_json
    orig_hash = records[1].record_hash

    with inject_audit_corruption(records, attack_type="tamper_payload", target_index=1):
        assert "malicious_tamper" in records[1].payload_json

    # Clean reversion
    assert records[1].payload_json == orig_json
    assert records[1].record_hash == orig_hash


# ── Test SHAPFailureInjector ──────────────────────────────────────────────────

def test_shap_failure_injector_lifecycle():
    from backend.app.xai.shap_explainer import SHAPExplainer

    mock_detector = SimpleNamespace(raw_model=object(), model_type="tree")
    explainer = object.__new__(SHAPExplainer)
    with inject_shap_failure(error_message="OOM in TreeExplainer"):
        with pytest.raises(RuntimeError) as exc_info:
            explainer.explain(None)
        assert "OOM in TreeExplainer" in str(exc_info.value)


# ── Test IncompleteExperimentInjector ─────────────────────────────────────────

def test_incomplete_experiment_injector_lifecycle():
    from backend.app.services.experiment_service import ExperimentService

    service = ExperimentService()
    with inject_incomplete_experiment("EXP-A", error_message="Worker terminated"):
        with pytest.raises(RuntimeError) as exc_info:
            service.run_exp_a({"n_samples": 50})
        assert "Worker terminated" in str(exc_info.value)


# ── Test MissingConfigurationInjector ─────────────────────────────────────────

def test_missing_configuration_injector_lifecycle():
    orig_name = settings.PROJECT_NAME
    with inject_missing_configuration({"PROJECT_NAME": "TEMPORARY_CHAOS"}):
        assert settings.PROJECT_NAME == "TEMPORARY_CHAOS"

    # Restored
    assert settings.PROJECT_NAME == orig_name


# ── Test UnavailableDependencyInjector ────────────────────────────────────────

def test_unavailable_dependency_injector_lifecycle():
    with inject_unavailable_dependency("fake_nonexistent_package_xyz"):
        with pytest.raises(ImportError) as exc_info:
            import fake_nonexistent_package_xyz
        assert "fake_nonexistent_package_xyz" in str(exc_info.value)


# ── Test InvalidAPIInputInjector ──────────────────────────────────────────────

def test_invalid_api_input_injector_payloads():
    payloads = InvalidAPIInputInjector.get_invalid_payloads()
    assert "non_uuid_id" in payloads
    assert "nan_features" in payloads
    assert "out_of_bounds_epsilon" in payloads


# ── Test Invariant Assertions ─────────────────────────────────────────────────

def test_invariant_assertions_pass_on_valid_inputs(db_session):
    # 1. assert_fails_safely on exception
    exc = PredictionFailedError("Model load failed")
    assert_fails_safely(exc)

    # 2. assert_meaningful_error
    assert_meaningful_error(exc, ["model", "failed"])

    # 3. assert_no_silent_invalid_results
    assert_no_silent_invalid_results(None)
    assert_no_silent_invalid_results({"status": "FAILED", "error": "something"})

    # 4. assert_consistent_state on clean db
    assert_consistent_state(db_session)

    # 5. assert_evidence_not_corrupted
    records = []
    prev = GENESIS_PREVIOUS_HASH
    for i in range(1, 3):
        p = {"i": i}
        pj = canonicalize(p)
        ph = calculate_payload_hash(p)
        rh = calculate_record_hash(prev, ph)
        records.append(SimpleNamespace(sequence_number=i, payload_json=pj, previous_hash=prev, record_hash=rh))
        prev = rh
    assert_evidence_not_corrupted(records, records)


def test_failure_verification_report_generation():
    report = FailureVerificationReport()
    record = FailureVerificationRecord(
        scenario_name="database_unavailable",
        fails_safely=True,
        reports_meaningful_error=True,
        no_silent_invalid_results=True,
        evidence_not_corrupted=True,
        maintains_consistent_state=True,
    )
    report.record(record)
    assert report.total_count == 1
    assert report.passed_count == 1
    assert report.all_passed is True

    summary = report.generate_summary()
    assert "database_unavailable" in summary
    assert "1/1 failure scenarios verified successfully." in summary
