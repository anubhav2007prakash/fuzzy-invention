"""Tests for the database integrity audit (phases 14/15).

Strategy: build a scratch SQLite DB with the real models, write a healthy
ledger, assert `consistent`; then inject each failure class (orphan
prediction, sequence gap, impossible timeline, dangling audit reference) and
assert it's detected with the right severity.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.models import Base, AuditRecord, ModelRecord, Prediction
from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    calculate_payload_hash,
    calculate_record_hash,
)
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.research.db_integrity import audit_database


@pytest.fixture()
def db():
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


def _add_model(db, **overrides):
    record = ModelRecord(
        name=overrides.get("name", "test-model"),
        artifact_path=overrides.get("artifact_path", "results/model.pkl"),
        preprocessing_path=overrides.get("preprocessing_path", "results/pre.pkl"),
        metrics_json="{}",
        feature_schema_json="[]",
    )
    db.add(record)
    db.flush()
    return record


def _add_prediction_with_audit(db, model, seq, previous_hash, payload_extra=None):
    payload = {"seq": seq, "model_id": model.id, **(payload_extra or {})}
    pj = canonicalize(payload)
    ph = calculate_payload_hash(payload)
    rh = calculate_record_hash(previous_hash, ph)
    prediction = Prediction(
        model_id=model.id,
        input_hash="a" * 64,
        predicted_class="0",
        probabilities_json=json.dumps({"0": 0.9, "1": 0.1}),
    )
    db.add(prediction)
    db.flush()
    db.add(AuditRecord(
        sequence_number=seq,
        prediction_id=prediction.id,
        payload_json=pj,
        previous_hash=previous_hash,
        record_hash=rh,
    ))
    db.flush()
    return prediction, rh


def test_healthy_database_is_consistent(db):
    model = _add_model(db)
    prev = GENESIS_PREVIOUS_HASH
    for seq in range(1, 4):
        _, prev = _add_prediction_with_audit(db, model, seq, prev)[0], None
        # recompute prev properly
        rec = db.query(AuditRecord).filter_by(sequence_number=seq).one()
        prev = rec.record_hash

    report = audit_database(db)
    assert report["consistent"] is True, report["findings"]
    assert report["summary"]["errors"] == 0
    assert report["chain_verification"]["verified"] is True
    assert report["total_records_checked"]["audit"] == 3


def test_orphan_prediction_detected(db):
    model = _add_model(db)
    prediction = Prediction(
        model_id="nonexistent-model-id",
        input_hash="a" * 64,
        predicted_class="0",
    )
    db.add(prediction)
    db.flush()

    report = audit_database(db)
    assert report["consistent"] is False
    orphans = [f for f in report["findings"] if f["check"] == "orphan_prediction"]
    assert len(orphans) == 1
    assert orphans[0]["severity"] == "ERROR"


def test_audit_sequence_gap_detected(db):
    model = _add_model(db)
    prev = GENESIS_PREVIOUS_HASH
    for seq in (1, 2, 4):  # skip 3 — simulates a deleted record
        _add_prediction_with_audit(db, model, seq, prev)
        rec = db.query(AuditRecord).filter_by(sequence_number=seq).one()
        prev = rec.record_hash

    report = audit_database(db)
    gaps = [f for f in report["findings"] if f["check"] == "audit_sequence_gap"]
    assert len(gaps) == 1
    assert gaps[0]["severity"] == "ERROR"
    assert 3 in gaps[0]["details"]["missing"]


def test_impossible_timeline_detected(db):
    """A prediction created before its model violates causality."""
    from datetime import datetime, timedelta

    model = _add_model(db)
    model.created_at = datetime.utcnow() + timedelta(hours=1)  # model "from the future"
    prediction = Prediction(
        model_id=model.id,
        input_hash="a" * 64,
        predicted_class="0",
        created_at=datetime.utcnow(),
    )
    db.add(prediction)
    db.flush()

    report = audit_database(db)
    impossible = [f for f in report["findings"] if f["check"] == "temporal_impossible"]
    assert len(impossible) == 1
    assert impossible[0]["severity"] == "ERROR"


def test_dangling_audit_reference_detected(db):
    model = _add_model(db)
    payload = {"seq": 1}
    pj = canonicalize(payload)
    ph = calculate_payload_hash(payload)
    rh = calculate_record_hash(GENESIS_PREVIOUS_HASH, ph)
    db.add(AuditRecord(
        sequence_number=1,
        prediction_id="missing-prediction-id",
        payload_json=pj,
        previous_hash=GENESIS_PREVIOUS_HASH,
        record_hash=rh,
    ))
    db.flush()

    report = audit_database(db)
    dangling = [f for f in report["findings"] if f["check"] == "audit_orphan_reference"]
    assert len(dangling) == 1
    assert dangling[0]["severity"] == "ERROR"
