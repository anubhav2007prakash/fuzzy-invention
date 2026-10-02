"""Researcher collaboration service (item 15).

Experiment ownership, comments, review status, approval, and derived
reproducibility / evidence status from stored result artifacts.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.db.models import ExperimentComment, ExperimentReviewState

logger = get_logger(__name__)

REVIEW_STATUSES = ("draft", "under_review", "changes_requested", "approved")
RESULTS_DIR = Path(settings.RESULTS_DIR)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CollaborationService:
    def __init__(self, db: Session):
        self.db = db

    # ── Comments ─────────────────────────────────────────────────────────────

    def add_comment(self, experiment_id: str, author: str, body: str) -> ExperimentComment:
        exp = (experiment_id or "").strip().upper()
        if not exp:
            raise ValueError("experiment_id must be a non-empty string.")
        if not author or not str(author).strip():
            raise ValueError("author must be a non-empty string.")
        if not body or not str(body).strip():
            raise ValueError("comment body must be a non-empty string.")
        comment = ExperimentComment(
            experiment_id=exp, author=str(author).strip(), body=str(body).strip()
        )
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def list_comments(self, experiment_id: str) -> List[Dict[str, Any]]:
        comments = (
            self.db.query(ExperimentComment)
            .filter_by(experiment_id=experiment_id.strip().upper())
            .order_by(ExperimentComment.created_at.asc())
            .all()
        )
        return [
            {
                "id": c.id,
                "experiment_id": c.experiment_id,
                "author": c.author,
                "body": c.body,
                "created_at": str(c.created_at),
            }
            for c in comments
        ]

    # ── Review state ─────────────────────────────────────────────────────────

    def get_state(self, experiment_id: str) -> ExperimentReviewState:
        exp = experiment_id.strip().upper()
        state = self.db.get(ExperimentReviewState, exp)
        if state is None:
            state = ExperimentReviewState(experiment_id=exp, reviewers_json="[]")
            self.db.add(state)
            self.db.commit()
            self.db.refresh(state)
        return state

    def update_state(
        self,
        experiment_id: str,
        owner: Optional[str] = None,
        review_status: Optional[str] = None,
        reviewer: Optional[str] = None,
        approve: Optional[bool] = None,
    ) -> ExperimentReviewState:
        state = self.get_state(experiment_id)

        if owner is not None:
            state.owner = str(owner).strip() or None
        if review_status is not None:
            status = review_status.strip().lower().replace(" ", "_")
            if status not in REVIEW_STATUSES:
                raise ValueError(
                    f"review_status must be one of {', '.join(REVIEW_STATUSES)}."
                )
            state.review_status = status
        if reviewer:
            reviewers = state.reviewers
            if reviewer.strip() not in reviewers:
                reviewers.append(reviewer.strip())
                state.reviewers = reviewers
        if approve is True:
            if not reviewer:
                raise ValueError("approval requires a reviewer name.")
            state.review_status = "approved"
            state.approved_by = reviewer.strip()
            state.approved_at = _utcnow()
        elif approve is False:
            state.approved_by = None
            state.approved_at = None
            if state.review_status == "approved":
                state.review_status = "under_review"

        state.updated_at = _utcnow()
        self.db.commit()
        self.db.refresh(state)
        return state

    # ── Derived status ───────────────────────────────────────────────────────

    def _result_status(self, experiment_id: str) -> Dict[str, Any]:
        from backend.app.services.experiment_service import EXPERIMENT_RESULT_FILES
        files = EXPERIMENT_RESULT_FILES
        exp = experiment_id.strip().upper()
        filename = files.get(exp)
        if not filename:
            return {
                "reproducibility_status": "unknown_experiment",
                "evidence_status": "unknown_experiment",
            }
        path = RESULTS_DIR / filename
        if not path.exists():
            return {
                "reproducibility_status": "not_run",
                "evidence_status": "no_result",
            }
        try:
            with open(path, "r", encoding="utf-8") as f:
                result = json.load(f)
        except Exception:
            return {
                "reproducibility_status": "unreadable_result",
                "evidence_status": "unreadable_result",
            }
        manifest_ok = bool(result.get("run_manifest"))
        evidence = (result.get("evidence_package") or {}).get("status", "not_exported")
        return {
            "reproducibility_status": "manifest_available" if manifest_ok else "manifest_missing",
            "evidence_status": evidence,
            "result_hash": result.get("result_hash"),
        }

    def status_view(self, experiment_id: str) -> Dict[str, Any]:
        """Single JSON blob for the UI: ownership, thread, review, evidence."""
        state = self.get_state(experiment_id)
        derived = self._result_status(experiment_id)
        return {
            "experiment_id": experiment_id.strip().upper(),
            "owner": state.owner,
            "review_status": state.review_status,
            "reviewers": state.reviewers,
            "approved_by": state.approved_by,
            "approved_at": str(state.approved_at) if state.approved_at else None,
            "comments": self.list_comments(experiment_id),
            **derived,
        }
