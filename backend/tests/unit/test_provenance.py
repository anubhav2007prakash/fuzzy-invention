"""Tests for the provenance graph and trust checklists."""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.database import Base
import backend.app.db.models  # noqa: F401
from backend.app.db.models import AuditRecord, Dataset, Explanation, ModelRecord, Prediction
from backend.app.research.provenance import (
    build_provenance_graph,
    experiment_trust_checklist,
    node_detail,
    prediction_trust_checklist,
)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    # dataset with its raw file actually on disk (integrity check needs it)
    from backend.app.core.config import settings
    data_raw = tmp_path / "raw"
    data_raw.mkdir(parents=True)
    (data_raw / "f.csv").write_text("dur,spkts,label\n1.0,10,0\n", encoding="utf-8")
    monkeypatch.setattr(settings, "DATA_RAW_DIR", data_raw)

    dataset = Dataset(id="d1", name="Flows", file_name="f.csv", file_hash="a" * 64,
                      row_count=100, feature_count=8, target_column="label")
    session.add(dataset)
    model = ModelRecord(id="m1", name="RF", version="v1", artifact_path="x.joblib",
                        preprocessing_path="p.pkl", metrics_json='{"seed": 42}',
                        feature_schema_json="[]", experiment_id="EXP-A")
    session.add(model)
    prediction = Prediction(id="p1", model_id="m1", input_hash="b" * 64,
                            predicted_class="1", latency_ms=1.5)
    session.add(prediction)
    session.add(Explanation(id="e1", prediction_id="p1", method="SHAP-Tree",
                            top_features_json='[{"feature": "dur", "shap_value": 0.4, "importance": 0.4}]',
                            base_value=0.1, stability_score=0.95))

    # real forward-linked chain block for p1 (trust check re-verifies it)
    from backend.app.cryptography.hash_chain import build_audit_record_hashes, GENESIS_PREVIOUS_HASH
    evidence = {
        "event_type": "INFERENCE", "prediction_id": "p1",
        "model_id": "m1", "predicted_class": "1",
        "input_hash": "b" * 64, "timestamp": "2026-09-23T00:00:00Z",
    }
    canonical, _, record_hash = build_audit_record_hashes(evidence, GENESIS_PREVIOUS_HASH)
    session.add(AuditRecord(id="a1", sequence_number=1, prediction_id="p1",
                            payload_json=canonical, previous_hash=GENESIS_PREVIOUS_HASH,
                            record_hash=record_hash))
    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_graph_contains_all_node_types(db):
    graph = build_provenance_graph(db)
    types = {n["type"] for n in graph["nodes"]}
    assert {"dataset", "model", "prediction", "explanation", "evidence"} <= types
    # EXP-A has a stored results file → experiment node exists
    assert any(n["id"] == "experiment:EXP-A" for n in graph["nodes"])


def test_graph_edges_link_the_chain(db):
    graph = build_provenance_graph(db)
    edges = {(e["source"], e["target"], e["type"]) for e in graph["edges"]}
    assert ("prediction:p1", "model:m1", "produced_by") in edges
    assert ("explanation:e1", "prediction:p1", "explains") in edges
    assert ("evidence:1", "prediction:p1", "anchors") in edges
    assert ("evidence:1", "evidence:0", "hash_links") not in edges  # seq 1 has no predecessor


def test_graph_exposes_instead_of_dropping_dangling_experiment_edges(db):
    db.query(ModelRecord).filter_by(id="m1").update({"experiment_id": "EXP-Z"})
    db.commit()

    graph = build_provenance_graph(db)
    assert any(
        edge["target"] == "experiment:EXP-Z"
        for edge in graph["edges"]
    )
    assert graph["integrity"] == "warning"
    assert any(
        warning["target"] == "experiment:EXP-Z"
        for warning in graph["integrity_warnings"]
    )


def test_node_detail_lookup(db):
    graph = build_provenance_graph(db)
    node = node_detail("prediction:p1", db=db)
    assert node["metadata"]["input_hash"] == "b" * 64
    assert node_detail("prediction:missing", db=db) is None


def test_prediction_trust_checklist_all_eight_checks(db):
    report = prediction_trust_checklist("p1", db=db)
    assert report["checks_total"] == 8
    assert {c["check"] for c in report["checks"]} == {
        "Dataset provenance", "Dataset integrity", "Model version recorded",
        "Experiment configuration recorded", "Random seed recorded",
        "Explanation available", "Audit evidence", "Reproducibility",
    }
    assert report["checks_passed"] == report["checks_total"]  # seeded chain is complete
    assert report["complete"] is True
    assert "not a numeric trust score" in report["scoring_note"]


def test_prediction_trust_checklist_missing_prediction(db):
    with pytest.raises(ValueError, match="not found"):
        prediction_trust_checklist("nope", db=db)


def test_experiment_trust_checklist():
    # EXP-A has been run in this suite → its stored result exists
    report = experiment_trust_checklist("EXP-A")
    assert report["checks_total"] == 8
    assert report["checks_passed"] >= 6
    assert any(c["check"] == "Random seed recorded" for c in report["checks"])


def test_experiment_trust_checklist_unknown_experiment():
    with pytest.raises(ValueError, match="Unknown experiment"):
        experiment_trust_checklist("EXP-Z")


def test_no_numeric_trust_score_anywhere(db):
    report = prediction_trust_checklist("p1", db=db)
    dumped = json.dumps(report)
    assert "trust_score" not in dumped
