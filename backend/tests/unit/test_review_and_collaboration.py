"""Tests for human-in-the-loop review and researcher collaboration."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.database import Base
import backend.app.db.models  # noqa: F401
from backend.app.db.models import AnalystReview, ModelRecord, Prediction
from backend.app.services.collaboration_service import CollaborationService
from backend.app.services.review_service import ReviewService


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    model = ModelRecord(id="m1", name="RF", version="v1.2.3",
                        artifact_path="x.joblib", preprocessing_path="p.pkl")
    session.add(model)
    session.add_all([
        Prediction(id="p1", model_id="m1", input_hash="a" * 64, predicted_class="1"),
        Prediction(id="p2", model_id="m1", input_hash="b" * 64, predicted_class="0"),
        Prediction(id="p3", model_id="m1", input_hash="c" * 64, predicted_class="1"),
    ])
    session.commit()
    yield session
    session.close()
    engine.dispose()


# ── HITL review (item 14) ────────────────────────────────────────────────────

def test_record_review_captures_full_context(db):
    service = ReviewService(db)
    review = service.record_review("p1", "confirmed", analyst="Alice",
                                   notes="matches packet capture")
    assert review.model_version == "v1.2.3"
    assert review.model_predicted_class == "1"
    assert review.audit_record_id is None  # no audit block seeded
    assert review.disagrees_with_model is False


def test_review_decision_validation(db):
    service = ReviewService(db)
    with pytest.raises(ValueError, match="human_decision"):
        service.record_review("p1", "maybe")
    with pytest.raises(ValueError, match="analyst"):
        service.record_review("p1", "confirmed", analyst="")


def test_review_unknown_prediction_404_shape(db):
    from backend.app.core.exceptions import PredictionNotFoundError
    with pytest.raises(PredictionNotFoundError):
        ReviewService(db).record_review("missing", "confirmed")


def test_disagreement_stats(db):
    service = ReviewService(db)
    service.record_review("p1", "confirmed", analyst="Alice")
    service.record_review("p2", "rejected", analyst="Bob", notes="false positive")
    service.record_review("p3", "confirmed", analyst="Bob")

    stats = service.disagreement_stats()
    assert stats["total_reviews"] == 3
    assert stats["rejected"] == 1
    assert stats["disagreement_rate"] == round(1 / 3, 4)
    assert stats["by_analyst"]["Bob"]["disagreement_rate"] == round(1 / 2, 4)
    assert "disagrees with the model" in stats["interpretation"]


def test_review_idempotent_resubmission(db):
    service = ReviewService(db)
    first = service.record_review("p1", "confirmed", analyst="Alice")
    again = service.record_review("p1", "confirmed", analyst="Alice")
    assert first.id == again.id
    assert db.query(AnalystReview).count() == 1


def test_list_reviews_includes_explanation_none(db):
    service = ReviewService(db)
    service.record_review("p1", "rejected", analyst="Bob")
    items = service.list_reviews(decision="rejected")
    assert len(items) == 1
    assert items[0]["disagrees_with_model"] is True
    assert items[0]["explanation"] is None


# ── Collaboration (item 15) ──────────────────────────────────────────────────

def test_comment_round_trip(db):
    service = CollaborationService(db)
    service.add_comment("EXP-A", "researcher-a", "Ran with 3 repetitions.")
    service.add_comment("EXP-A", "researcher-b", "Reproduced; hashes match.")
    comments = service.list_comments("EXP-A")
    assert [c["author"] for c in comments] == ["researcher-a", "researcher-b"]
    assert "Reproduced" in comments[1]["body"]


def test_comment_validation(db):
    service = CollaborationService(db)
    with pytest.raises(ValueError, match="body"):
        service.add_comment("EXP-A", "researcher-a", "  ")


def test_review_state_lifecycle(db):
    service = CollaborationService(db)
    service.update_state("EXP-A", owner="researcher-a")
    service.update_state("EXP-A", review_status="under_review", reviewer="researcher-b")
    status_view = service.status_view("EXP-A")
    assert status_view["owner"] == "researcher-a"
    assert status_view["review_status"] == "under_review"
    assert status_view["reviewers"] == ["researcher-b"]
    assert status_view["evidence_status"] in ("not_exported", "exported")

    service.update_state("EXP-A", reviewer="researcher-b", approve=True)
    final = service.status_view("EXP-A")
    assert final["review_status"] == "approved"
    assert final["approved_by"] == "researcher-b"


def test_invalid_review_status_rejected(db):
    service = CollaborationService(db)
    with pytest.raises(ValueError, match="review_status"):
        service.update_state("EXP-A", review_status="vibes")


def test_unknown_experiment_status_is_derived_not_crashing(db):
    view = CollaborationService(db).status_view("EXP-Q")
    assert view["reproducibility_status"] == "unknown_experiment"


def test_status_view_includes_result_derived_state(db):
    view = CollaborationService(db).status_view("EXP-A")
    assert view["result_hash"]  # EXP-A has been run by the experiment tests
