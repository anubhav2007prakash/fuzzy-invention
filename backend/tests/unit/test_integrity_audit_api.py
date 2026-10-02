from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.v1.router import api_router
from backend.app.db.models import ArtifactLineage, Base, Prediction
from backend.app.research.integrity_audit import audit_database


def _make_db() -> tuple[Session, object]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return session, engine


def test_audit_detects_corrupt_fk_lineage_and_missing_provenance():
    db, engine = _make_db()
    try:
        db.execute(text("PRAGMA foreign_keys=OFF"))
        db.add(
            Prediction(
                id="prediction-orphan",
                model_id="missing-model",
                input_hash="a" * 64,
                predicted_class="benign",
            )
        )
        db.add(
            ArtifactLineage(
                artifact_id="artifact-orphan",
                artifact_type="model",
                parent_artifact_id="missing-parent",
                version="v1",
                sha256="not-a-digest",
                metadata_json="[]",
            )
        )
        db.add_all(
            [
                ArtifactLineage(
                    artifact_id="cycle-a",
                    artifact_type="model",
                    parent_artifact_id="cycle-b",
                    version="v1",
                    sha256="a" * 64,
                    metadata_json="{}",
                ),
                ArtifactLineage(
                    artifact_id="cycle-b",
                    artifact_type="model",
                    parent_artifact_id="cycle-a",
                    version="v1",
                    sha256="b" * 64,
                    metadata_json="{}",
                ),
            ]
        )
        db.commit()

        report = audit_database(db)
        types = {finding["type"] for finding in report["findings"]}
        assert "orphan_foreign_key" in types
        assert "missing_provenance" in types
        assert "invalid_artifact_digest" in types
        assert "invalid_metadata" in types
        assert "invalid_relationship" in types
        assert report["status"] == "UNHEALTHY"
        assert report["read_only"] is True
    finally:
        db.close()
        engine.dispose()


def test_audit_does_not_mutate_database():
    db, engine = _make_db()
    try:
        db.add(
            ArtifactLineage(
                artifact_id="valid-root",
                artifact_type="dataset",
                version="v1",
                sha256="a" * 64,
                metadata_json="{}",
            )
        )
        db.commit()
        before = db.execute(text("SELECT total_changes()")).scalar_one()
        pending = Prediction(
            id="pending-not-flushed",
            model_id="not-present",
            input_hash="b" * 64,
            predicted_class="benign",
        )
        db.add(pending)
        audit_database(db)
        after = db.execute(text("SELECT total_changes()")).scalar_one()
        assert after == before
        assert pending in db.new
        assert not db.dirty
        assert not db.deleted
    finally:
        db.close()
        engine.dispose()


def test_integrity_endpoint_is_mounted_at_requested_path():
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    path_method_pairs = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }
    assert ("/api/v1/integrity/database/verify", "POST") in path_method_pairs
