"""Human-in-the-loop review + researcher collaboration models (items 14/15)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _uuid() -> str:
    return str(uuid.uuid4())


class AnalystReview(Base):
    """One human decision about one model prediction (item 14)."""

    __tablename__ = "analyst_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    prediction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("predictions.id"), nullable=False
    )
    model_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model_predicted_class: Mapped[str] = mapped_column(String(50), nullable=False)
    human_decision: Mapped[str] = mapped_column(String(20), nullable=False)  # confirmed | rejected
    analyst: Mapped[str] = mapped_column(String(120), nullable=False, default="analyst")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audit_record_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_analyst_reviews_prediction_id", "prediction_id"),
        Index("ix_analyst_reviews_decision", "human_decision"),
    )

    prediction = relationship("Prediction", back_populates="reviews")

    @property
    def disagrees_with_model(self) -> bool:
        return self.human_decision == "rejected"


class ExperimentComment(Base):
    """Collaboration thread entry on an experiment (item 15)."""

    __tablename__ = "experiment_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    experiment_id: Mapped[str] = mapped_column(String(50), nullable=False)
    author: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (Index("ix_experiment_comments_experiment_id", "experiment_id"),)


class ExperimentReviewState(Base):
    """Review status / approval / reproducibility & evidence status (item 15)."""

    __tablename__ = "experiment_review_states"

    experiment_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    owner: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="draft"
    )  # draft | under_review | changes_requested | approved
    reviewers_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    approved_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    @property
    def reviewers(self) -> list:
        try:
            return json.loads(self.reviewers_json or "[]")
        except Exception:
            return []

    @reviewers.setter
    def reviewers(self, value: list) -> None:
        self.reviewers_json = json.dumps(value)
