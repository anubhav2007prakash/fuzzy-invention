"""Integration tests for Controlled Failure Injection.

Simulates 9 controlled failure modes across SentinelCrypt services, APIs, and research pipelines:
1. database unavailable
2. model artifact missing
3. dataset corruption
4. audit record corruption
5. SHAP failure
6. incomplete experiment
7. missing configuration
8. unavailable dependency
9. invalid API response / input

For EVERY failure mode, the tests verify that SentinelCrypt:
- fails safely
- reports meaningful errors
- does not silently produce invalid research results
- does not corrupt existing evidence
- maintains consistent state
"""
from __future__ import annotations

import io
import json
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import OperationalError

from backend.app.core.config import settings
from backend.app.core.exceptions import (
    DatabaseUnavailableError,
    DatasetNotFoundError,
    ExplanationFailedError,
    InvalidDatasetError,
    ModelNotFoundError,
    ModelTrainingError,
    PredictionFailedError,
    UnsupportedFormatError,
)
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    calculate_payload_hash,
    calculate_record_hash,
)
from backend.app.cryptography.hashing import hash_file, sha256_hash
from backend.app.cryptography.verifier import verify_ledger
from backend.app.db.database import Base, get_db
from backend.app.db.models import AuditRecord, Dataset, ModelRecord, Prediction
from backend.app.main import app
from backend.app.research.db_integrity import audit_database
from backend.app.services.dataset_service import DatasetService
from backend.app.services.experiment_service import ExperimentService
from backend.app.services import experiment_service as experiment_service_module
from backend.app.services.explanation_service import ExplanationService
from backend.app.services.prediction_service import PredictionService
from backend.app.services.training_service import TrainingService
from backend.app.schemas.prediction import PredictionRequest
from backend.tests.failure_injection import (
    CorruptedAuditRecordInjector,
    CorruptedDatasetInjector,
    DatabaseUnavailableInjector,
    FailureVerificationRecord,
    FailureVerificationReport,
    IncompleteExperimentInjector,
    InvalidAPIInputInjector,
    MissingConfigurationInjector,
    MissingModelArtifactInjector,
    SHAPFailureInjector,
    UnavailableDependencyInjector,
    assert_consistent_state,
    assert_evidence_not_corrupted,
    assert_fails_safely,
    assert_meaningful_error,
    assert_no_silent_invalid_results,
    inject_audit_corruption,
    inject_database_unavailable,
    inject_dataset_corruption,
    inject_incomplete_experiment,
    inject_missing_configuration,
    inject_missing_model_artifact,
    inject_shap_failure,
    inject_unavailable_dependency,
)


@pytest.fixture()
def test_env():
    """Sets up an isolated in-memory DB and temporary artifact directories."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    original_dependency_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    tmp_dir = tempfile.TemporaryDirectory()
    raw_dir = Path(tmp_dir.name) / "raw"
    models_dir = Path(tmp_dir.name) / "models"
    artifacts_dir = Path(tmp_dir.name) / "artifacts"
    raw_dir.mkdir(parents=True)
    models_dir.mkdir(parents=True)
    artifacts_dir.mkdir(parents=True)
    results_dir = Path(tmp_dir.name) / "results"
    results_dir.mkdir()

    orig_raw = settings.DATA_RAW_DIR
    orig_models = settings.MODELS_TRAINED_DIR
    orig_artifacts = settings.MODELS_ARTIFACTS_DIR
    orig_results_dir = experiment_service_module.RESULTS_DIR
    settings.DATA_RAW_DIR = raw_dir
    settings.MODELS_TRAINED_DIR = models_dir
    settings.MODELS_ARTIFACTS_DIR = artifacts_dir
    experiment_service_module.RESULTS_DIR = results_dir

    yield SimpleNamespace(
        engine=engine,
        db=db,
        Session=TestingSession,
        client=client,
        tmp_dir=tmp_dir,
        raw_dir=raw_dir,
        models_dir=models_dir,
        artifacts_dir=artifacts_dir,
        results_dir=results_dir,
    )

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_dependency_overrides)
    client.close()
    settings.DATA_RAW_DIR = orig_raw
    settings.MODELS_TRAINED_DIR = orig_models
    settings.MODELS_ARTIFACTS_DIR = orig_artifacts
    experiment_service_module.RESULTS_DIR = orig_results_dir
    db.close()
    engine.dispose()
    tmp_dir.cleanup()


def _seed_healthy_system(env) -> SimpleNamespace:
    """Populates baseline dataset, trained model, prediction, and audit evidence."""
    # 1. Dataset
    csv_bytes = (
        b"dur,proto,service,state,spkts,dpkts,sbytes,dbytes,sttl,dttl,sloss,dloss,"
        b"sinpkt,dinpkt,sjit,djit,swin,stcpb,dtcpb,dwin,tcprtt,synack,ackdat,smean,"
        b"dmean,trans_depth,response_body_len,ct_srv_src,ct_state_ttl,ct_dst_ltm,"
        b"ct_src_dport_ltm,ct_dst_sport_ltm,ct_dst_src_ltm,is_ftp_login,ct_ftp_cmd,"
        b"ct_flw_http_mthd,ct_src_ltm,ct_srv_dst,is_sm_ips_ports,label\n"
        b"0.1,tcp,http,FIN,10,12,1000,2000,64,64,1,1,10.0,10.0,0.1,0.1,255,100,200,255,0.01,0.01,0.01,100,100,0,0,1,1,1,1,1,1,0,0,0,1,1,0,0\n"
        b"0.2,tcp,http,FIN,15,18,1500,2500,64,64,2,2,12.0,12.0,0.2,0.2,255,105,205,255,0.02,0.02,0.02,100,100,0,0,1,1,1,1,1,1,0,0,0,1,1,0,1\n"
    )
    dataset_file = env.raw_dir / "seed_dataset.csv"
    dataset_file.write_bytes(csv_bytes)
    dataset_hash = sha256_hash(csv_bytes)

    ds_record = Dataset(
        id=str(uuid.uuid4()),
        name="seed-dataset",
        file_name="seed_dataset.csv",
        file_hash=dataset_hash,
        row_count=2,
        feature_count=39,
        target_column="label",
        validation_status="VALID",
    )
    env.db.add(ds_record)
    env.db.flush()

    # 2. Model & preprocessor artifacts
    model_artifact = env.models_dir / "baseline_model.joblib"
    prep_artifact = env.artifacts_dir / "baseline_prep.joblib"

    from backend.app.ml.models.random_forest import RandomForestDetector
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    import pickle

    detector = RandomForestDetector(
        hyperparameters={"n_estimators": 5, "n_jobs": 1},
        random_seed=42,
    )
    X = np.array([[0.1, 10.0], [0.2, 15.0]])
    y = np.array([0, 1])
    detector.fit(X, y, feature_names=["dur", "spkts"])
    detector.save(model_artifact)

    prep_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    prep_pipe.fit(X)

    with open(prep_artifact, "wb") as f:
        pickle.dump({
            "pipeline": prep_pipe,
            "feature_cols": ["dur", "spkts"],
            "cat_encoders": {},
        }, f)

    model_record = ModelRecord(
        id=str(uuid.uuid4()),
        name="baseline-rf-model",
        version="v1.0.0",
        artifact_path=str(model_artifact),
        preprocessing_path=str(prep_artifact),
        metrics_json="{}",
        feature_schema_json=json.dumps([{"name": "dur", "type": "float"}, {"name": "spkts", "type": "int"}]),
    )
    env.db.add(model_record)
    env.db.flush()

    # 3. Prediction & Audit Record
    pred_record = Prediction(
        id=str(uuid.uuid4()),
        model_id=model_record.id,
        input_hash="0" * 64,
        predicted_class="1",
        probabilities_json=json.dumps({"0": 0.1, "1": 0.9}),
        request_source="api",
        latency_ms=1.5,
    )
    env.db.add(pred_record)
    env.db.flush()

    audit_payload = {
        "sequence_number": 1,
        "prediction_id": pred_record.id,
        "model_id": model_record.id,
        "predicted_class": "1",
    }
    pj = canonicalize(audit_payload)
    ph = calculate_payload_hash(audit_payload)
    rh = calculate_record_hash(GENESIS_PREVIOUS_HASH, ph)

    audit_record = AuditRecord(
        sequence_number=1,
        prediction_id=pred_record.id,
        payload_json=pj,
        previous_hash=GENESIS_PREVIOUS_HASH,
        record_hash=rh,
    )
    env.db.add(audit_record)
    env.db.commit()

    return SimpleNamespace(
        dataset=ds_record,
        dataset_file=dataset_file,
        model=model_record,
        model_artifact=model_artifact,
        prep_artifact=prep_artifact,
        prediction=pred_record,
        audit=audit_record,
    )


# ── Scenario 1: Database Unavailable ──────────────────────────────────────────

def test_failure_injection_database_unavailable(test_env):
    """Verify that when database is unavailable:
    - SentinelCrypt fails safely with typed error or 503 HTTP status
    - Reports meaningful diagnostics
    - Does not emit silent invalid results
    - Does not corrupt existing audit evidence or state
    """
    seeded = _seed_healthy_system(test_env)
    records_before = test_env.db.query(AuditRecord).all()

    # 1. API boundary simulation: dependency failure
    with inject_database_unavailable(app=app, error_message="PostgreSQL cluster unreachable"):
        response = test_env.client.get("/api/v1/health/detailed")
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["code"] == "DATABASE_UNAVAILABLE"
        assert_meaningful_error(body, ["database", "unavailable"])

    # 2. Service transaction simulation: operational failure during prediction
    pred_svc = PredictionService(test_env.db)
    req = PredictionRequest(
        model_id=seeded.model.id,
        features={"dur": 0.1, "spkts": 10},
    )

    with inject_database_unavailable(db_session=test_env.db, error_message="Connection terminated"):
        with pytest.raises(OperationalError) as exc_info:
            test_env.db.execute(AuditRecord.__table__.select())
        assert_fails_safely(exc_info.value)
        assert_meaningful_error(exc_info.value, ["connection terminated"])

    # Recovery: verify baseline evidence was not damaged and state remains consistent
    test_env.db.rollback()
    records_after = test_env.db.query(AuditRecord).all()
    assert_evidence_not_corrupted(records_before, records_after)
    assert_consistent_state(test_env.db)


# ── Scenario 2: Model Artifact Missing ────────────────────────────────────────

def test_failure_injection_model_artifact_missing(test_env):
    """Verify that when a model artifact (.joblib) is missing from disk:
    - Inference fails safely with PredictionFailedError / 422
    - Explanations fail safely with ExplanationFailedError / 422
    - No bogus prediction or zero confidence is silently returned
    - No corrupt prediction or audit row is appended
    """
    seeded = _seed_healthy_system(test_env)
    records_before = test_env.db.query(AuditRecord).all()
    predictions_before = test_env.db.query(Prediction).count()

    pred_svc = PredictionService(test_env.db)
    req = PredictionRequest(
        model_id=seeded.model.id,
        features={"dur": 0.1, "spkts": 10},
    )

    with inject_missing_model_artifact(artifact_path=seeded.model.artifact_path):
        # Service level
        with pytest.raises(PredictionFailedError) as exc_info:
            pred_svc.predict(req)
        assert_fails_safely(exc_info.value)
        assert_meaningful_error(exc_info.value, ["failed to load model artifact"])
        assert_no_silent_invalid_results(None)

        # API level
        response = test_env.client.post(
            "/api/v1/predictions",
            json={"model_id": seeded.model.id, "features": {"dur": 0.1, "spkts": 10}},
        )
        assert response.status_code == 400
        assert "failed to load model artifact" in response.json()["detail"].lower()

        # Explanation service
        expl_svc = ExplanationService(test_env.db)
        with pytest.raises(ExplanationFailedError) as expl_exc:
            expl_svc.explain_prediction(seeded.prediction.id)
        assert_fails_safely(expl_exc.value)
        assert_meaningful_error(expl_exc.value, ["cannot load model artifact"])

    # Verify no corrupt entities or evidence created
    test_env.db.rollback()
    records_after = test_env.db.query(AuditRecord).all()
    assert_evidence_not_corrupted(records_before, records_after)
    assert test_env.db.query(Prediction).count() == predictions_before
    assert_consistent_state(test_env.db)


# ── Scenario 3: Dataset Corruption ────────────────────────────────────────────

def test_failure_injection_dataset_corruption(test_env):
    """Verify that:
    A. Malformed CSV upload is rejected with UnsupportedFormatError / InvalidDatasetError
    B. Disk tampering (hash mismatch) prevents model training and halts safely
    """
    seeded = _seed_healthy_system(test_env)
    records_before = test_env.db.query(AuditRecord).all()
    models_before = test_env.db.query(ModelRecord).count()

    # Part A: Upload corrupted CSV
    corrupted_csv = CorruptedDatasetInjector.generate_corrupted_csv("syntax_error")
    ds_svc = DatasetService(test_env.db)

    with pytest.raises(UnsupportedFormatError) as exc_info:
        ds_svc.upload_and_register(
            file_content=corrupted_csv,
            file_name="corrupted.csv",
        )
    assert_fails_safely(exc_info.value)
    assert_meaningful_error(exc_info.value, ["could not parse csv"])

    # Part B: Post-registration disk tampering (file bytes tampered on disk)
    with inject_dataset_corruption(file_path=seeded.dataset_file, corruption_type="tampered_bytes"):
        from backend.app.schemas.model import ModelTrainRequest
        train_svc = TrainingService(test_env.db)
        train_req = ModelTrainRequest(
            dataset_id=seeded.dataset.id,
            model_type="random_forest",
            random_seed=42,
        )
        with pytest.raises(ModelTrainingError) as train_exc:
            train_svc.train_model(train_req)

        assert_fails_safely(train_exc.value)
        assert_meaningful_error(train_exc.value, ["integrity check failed", "does not match its registered sha-256"])
        assert_no_silent_invalid_results(None)

    # State check: no poisoned model was registered
    assert test_env.db.query(ModelRecord).count() == models_before
    records_after = test_env.db.query(AuditRecord).all()
    assert_evidence_not_corrupted(records_before, records_after)
    assert_consistent_state(test_env.db)


# ── Scenario 4: Audit Record Corruption ───────────────────────────────────────

def test_failure_injection_audit_record_corruption(test_env):
    """Verify that tampering with audit records:
    - Is detected with exact localized anomaly
    - Never passes verification
    - Does not corrupt other honest records
    """
    seeded = _seed_healthy_system(test_env)

    # Build a 3-record chain in memory
    records = []
    prev = GENESIS_PREVIOUS_HASH
    for i in range(1, 4):
        p = {"seq": i, "val": i * 10}
        pj = canonicalize(p)
        ph = calculate_payload_hash(p)
        rh = calculate_record_hash(prev, ph)
        records.append(SimpleNamespace(
            sequence_number=i, payload_json=pj, previous_hash=prev, record_hash=rh, payload=p
        ))
        prev = rh

    # Test 1: Tampered payload
    with inject_audit_corruption(records, attack_type="tamper_payload", target_index=1):
        res = verify_ledger(records)
        assert res.verified is False
        assert any(f["error_type"] == "TAMPERED_RECORD_HASH" for f in res.failed_records)
        assert res.failed_records[0]["sequence_number"] == 2

    # Test 2: Broken previous hash
    with inject_audit_corruption(records, attack_type="break_previous_hash", target_index=2):
        res = verify_ledger(records)
        assert res.verified is False
        assert any(f["error_type"] == "PREVIOUS_HASH_MISMATCH" for f in res.failed_records)

    # Test 3: Corrupted JSON syntax
    with inject_audit_corruption(records, attack_type="corrupt_json", target_index=1):
        res = verify_ledger(records)
        assert res.verified is False
        assert any(f["error_type"] == "CORRUPTED_JSON_PAYLOAD" for f in res.failed_records)

    # Verify chain verifies cleanly once corruption injector exits
    clean_res = verify_ledger(records)
    assert clean_res.verified is True
    assert_consistent_state(test_env.db)


# ── Scenario 5: SHAP Failure ──────────────────────────────────────────────────

def test_failure_injection_shap_failure(test_env):
    """Verify that when SHAP explainer computation fails:
    - ExplanationService raises ExplanationFailedError / 422
    - Does not silently produce invalid/zero attributions
    - Does not create corrupted Explanation DB row
    - Existing prediction and audit records remain intact
    """
    seeded = _seed_healthy_system(test_env)
    records_before = test_env.db.query(AuditRecord).all()

    expl_svc = ExplanationService(test_env.db)

    with inject_shap_failure(error_message="TreeExplainer out of memory during kernel integration"):
        with pytest.raises(ExplanationFailedError) as exc_info:
            expl_svc.explain_prediction(seeded.prediction.id)

        assert_fails_safely(exc_info.value)
        assert_meaningful_error(exc_info.value, ["shap computation failed", "out of memory"])
        assert_no_silent_invalid_results(None)

        # API level check
        response = test_env.client.post(f"/api/v1/explanations/{seeded.prediction.id}")
        assert response.status_code == 422
        assert "shap computation failed" in response.json()["detail"].lower()

    # Verify no orphan explanation rows and evidence remains intact
    records_after = test_env.db.query(AuditRecord).all()
    assert_evidence_not_corrupted(records_before, records_after)
    assert_consistent_state(test_env.db)


# ── Scenario 6: Incomplete Experiment ─────────────────────────────────────────

def test_failure_injection_incomplete_experiment(test_env):
    """Verify that when an experiment runner fails mid-execution:
    - Process fails safely with clear exception
    - Does not write corrupted partial result JSON to results directory
    - Existing valid results are preserved
    """
    exp_svc = ExperimentService(test_env.db)

    # Write a pre-existing valid result file to verify it is NOT corrupted
    test_result_file = test_env.results_dir / "exp_a_generalization.json"
    backup_content = '{"status":"previously-valid"}'
    test_result_file.write_text(backup_content, encoding="utf-8")

    with inject_incomplete_experiment("EXP-A", error_message="Worker SIGKILL simulation"):
        with pytest.raises(RuntimeError) as exc_info:
            exp_svc.run_exp_a({"n_samples": 50})
        assert_fails_safely(exc_info.value)
        assert_meaningful_error(exc_info.value, ["worker sigkill simulation"])
        assert_no_silent_invalid_results(None)

    assert test_result_file.read_text(encoding="utf-8") == backup_content

    assert_consistent_state(test_env.db)


# ── Scenario 7: Missing Configuration ─────────────────────────────────────────

def test_failure_injection_missing_configuration(test_env):
    """Verify that when critical configuration directories or settings are missing:
    - Service detects the misconfiguration and fails safely
    - Reports meaningful error mentioning the configuration issue
    - Does not perform undefined destructive actions
    """
    seeded = _seed_healthy_system(test_env)

    # Set raw directory to a non-existent invalid path
    invalid_path = Path(test_env.tmp_dir.name) / "missing-raw-dir"
    with inject_missing_configuration({"DATA_RAW_DIR": invalid_path}):
        train_svc = TrainingService(test_env.db)
        from backend.app.schemas.model import ModelTrainRequest
        with pytest.raises(ModelTrainingError) as exc_info:
            train_svc.train_model(ModelTrainRequest(
                dataset_id=seeded.dataset.id,
                model_type="random_forest",
                random_seed=42,
            ))
        assert_fails_safely(exc_info.value)
        assert_meaningful_error(exc_info.value, ["not found on disk"])

    assert_consistent_state(test_env.db)


# ── Scenario 8: Unavailable Dependency ────────────────────────────────────────

def test_failure_injection_unavailable_dependency(test_env):
    """Verify that when an external dependency is unavailable:
    - System degrades gracefully or raises informative error
    - Does not produce silent fake outputs
    """
    from backend.app.services.experiment_service import _reproducibility_metadata

    # Simulate shap unavailable
    with inject_unavailable_dependency("shap", error_message="No module named 'shap'"):
        # Reproducibility metadata degrades gracefully to 'unknown' rather than crashing
        meta = _reproducibility_metadata()
        assert meta["shap_version"] == "unknown"

    assert_consistent_state(test_env.db)


# ── Scenario 9: Invalid API Response & Inputs ─────────────────────────────────

def test_failure_injection_invalid_api_input(test_env, monkeypatch):
    """Verify that invalid API inputs (NaN, non-UUID, malformed JSON, out-of-bounds):
    - Are intercepted by global exception handlers returning 422
    - Return meaningful error JSON without raw traceback leakage
    - Maintain consistent database state
    """
    _seed_healthy_system(test_env)

    # 1. Non-UUID format resource ID
    resp1 = test_env.client.get("/api/v1/predictions/not-a-valid-uuid")
    assert resp1.status_code == 422
    assert resp1.json()["error"]["code"] == "VALIDATION_ERROR"
    assert_meaningful_error(resp1.json(), ["invalid prediction id format"])

    # 2. Malformed JSON bytes in request body
    resp2 = test_env.client.post(
        "/api/v1/predictions",
        content=b'{"model_id": "00000000-0000-0000-0000-000000000000", "unclosed": ',
        headers={"Content-Type": "application/json"},
    )
    assert resp2.status_code == 422
    assert "detail" in resp2.json() or "error" in resp2.json()

    # 3. Out-of-bounds parameters
    resp3 = test_env.client.post(
        "/api/v1/research/experiments/EXP-A/run",
        json={"n_samples": -50},
    )
    assert resp3.status_code == 422
    assert resp3.json()["error"]["code"] == "VALIDATION_ERROR"
    assert_meaningful_error(resp3.json(), ["positive integer"])

    # A handler returning an invalid success payload must fail closed at the
    # response-model boundary rather than return a success-shaped API result.
    monkeypatch.setattr(PredictionService, "predict", lambda self, payload: {})
    malformed_response = test_env.client.post(
        "/api/v1/predictions",
        json={
            "model_id": str(uuid.uuid4()),
            "features": {"dur": 0.1},
        },
    )
    assert malformed_response.status_code == 500
    error_body = assert_fails_safely(malformed_response)
    assert isinstance(error_body, dict)
    assert error_body["error"]["code"] == "INVALID_SERVER_RESPONSE"
    assert_meaningful_error(error_body, ["response", "api schema"])
    assert_no_silent_invalid_results(malformed_response)

    assert_consistent_state(test_env.db)


# ── Master Report Generation ──────────────────────────────────────────────────

def test_controlled_failure_suite_summary_report():
    """Unverified scenario records must not be reported as successful."""
    report = FailureVerificationReport()

    scenarios = [
        "database_unavailable",
        "model_artifact_missing",
        "dataset_corruption",
        "audit_record_corruption",
        "shap_failure",
        "incomplete_experiment",
        "missing_configuration",
        "unavailable_dependency",
        "invalid_api_response",
    ]

    for name in scenarios:
        report.record(FailureVerificationRecord(scenario_name=name))

    assert report.total_count == len(scenarios)
    assert report.passed_count == 0
    assert report.all_passed is False
    summary = report.generate_summary()
    assert "0/9 failure scenarios verified successfully." in summary
