import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.database import Base
import backend.app.db.models  # noqa: F401
from backend.app.db.models import ArtifactLineage
from backend.app.services.lineage_service import (
    ArtifactLineageService,
    LineageIntegrityError,
    artifact_digest,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def artifact(artifact_id, artifact_type="source", parent=None, payload=None):
    return {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "parent_artifact_id": parent,
        "version": "1",
        "sha256": artifact_digest(payload or {"id": artifact_id}),
        "metadata": {"payload": payload or {"id": artifact_id}},
    }


def test_records_parent_first_chain_and_returns_explicit_edges(db):
    service = ArtifactLineageService(db)
    service.record_chain([
        artifact("raw:1"),
        artifact("validated:1", "validated_dataset", "raw:1"),
        artifact("processed:1", "processed_dataset", "validated:1"),
    ])

    graph = service.graph()
    assert graph["integrity"] == "structurally_valid"
    assert {node["artifact_id"] for node in graph["nodes"]} == {
        "raw:1", "validated:1", "processed:1",
    }
    assert graph["edges"] == [
        {"source": "raw:1", "target": "validated:1", "type": "derived_from"},
        {"source": "validated:1", "target": "processed:1", "type": "derived_from"},
    ]


def test_rejects_nonexistent_parent_without_persisting_any_chain_nodes(db):
    service = ArtifactLineageService(db)
    with pytest.raises(LineageIntegrityError, match="does not exist"):
        service.record_chain([artifact("orphan:1", parent="missing:1")])
    assert db.query(ArtifactLineage).count() == 0


def test_rejects_conflicting_reuse_of_artifact_id(db):
    service = ArtifactLineageService(db)
    service.record_chain([artifact("artifact:1", payload={"revision": 1})])
    with pytest.raises(LineageIntegrityError, match="conflicting lineage"):
        service.record_chain([artifact("artifact:1", payload={"revision": 2})])
    assert db.query(ArtifactLineage).count() == 1


def test_identical_retries_are_idempotent(db):
    service = ArtifactLineageService(db)
    item = artifact("stable:1")
    first = service.record_chain([item])[0]
    second = service.record_chain([item])[0]
    assert first.artifact_id == second.artifact_id
    assert db.query(ArtifactLineage).count() == 1


def test_rejects_malformed_digest_and_non_finite_metadata(db):
    service = ArtifactLineageService(db)
    invalid_digest = artifact("invalid-digest:1")
    invalid_digest["sha256"] = "not-a-sha256"
    with pytest.raises(LineageIntegrityError, match="lowercase SHA-256"):
        service.record_chain([invalid_digest])

    invalid_metadata = artifact("invalid-metadata:1")
    invalid_metadata["metadata"] = {"value": float("nan")}
    with pytest.raises(LineageIntegrityError, match="not canonicalizable JSON"):
        service.record_chain([invalid_metadata])
    assert db.query(ArtifactLineage).count() == 0


def test_graph_refuses_manually_introduced_dangling_parent(db):
    service = ArtifactLineageService(db)
    service.record_chain([artifact("child:1")])
    db.query(ArtifactLineage).filter_by(artifact_id="child:1").update({
        ArtifactLineage.parent_artifact_id: "deleted-parent:1",
    })
    db.commit()

    with pytest.raises(LineageIntegrityError, match="missing parent"):
        service.graph()


def test_graph_refuses_manually_introduced_cycle(db):
    service = ArtifactLineageService(db)
    service.record_chain([artifact("first:1"), artifact("second:1", parent="first:1")])
    db.query(ArtifactLineage).filter_by(artifact_id="first:1").update({
        ArtifactLineage.parent_artifact_id: "second:1",
    })
    db.commit()

    with pytest.raises(LineageIntegrityError, match="cycle detected"):
        service.graph()


def test_api_returns_persisted_lineage_and_reports_integrity_failure(db):
    from fastapi import HTTPException
    from backend.app.api.v1.research import artifact_lineage

    service = ArtifactLineageService(db)
    service.record_chain([artifact("root:1")])
    response = artifact_lineage(db)
    assert response["nodes"][0]["artifact_id"] == "root:1"

    db.query(ArtifactLineage).filter_by(artifact_id="root:1").update({
        ArtifactLineage.parent_artifact_id: "missing:parent",
    })
    db.commit()
    with pytest.raises(HTTPException) as exc:
        artifact_lineage(db)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "LINEAGE_INTEGRITY_ERROR"
