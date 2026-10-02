"""Human-in-the-loop review service (item 14).

Records model prediction + explanation + human decision + timestamp +
model version + audit evidence, and computes disagreement statistics
(how often does human review reject the model?).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.core.exceptions import PredictionNotFoundError
from backend.app.core.logging import get_logger
from backend.app.db.models import AnalystReview, AuditRecord, Explanation, ModelRecord, Prediction

logger = get_logger(__name__)

DECISIONS = ("confirmed", "rejected")


class ReviewService:
    def __init__(self, db: Session):
        self.db = db

    def record_review(
        self,
        prediction_id: str,
        human_decision: str,
        analyst: str = "analyst",
        notes: Optional[str] = None,
    ) -> AnalystReview:
        """Attach a human decision to an existing prediction (with full context)."""
        decision = (human_decision or "").strip().lower()
        if decision not in DECISIONS:
            raise ValueError(
                f"human_decision must be one of {', '.join(DECISIONS)}; got '{human_decision}'."
            )
        if not analyst or not str(analyst).strip():
            raise ValueError("analyst must be a non-empty string.")

        prediction = self.db.get(Prediction, prediction_id)
        if not prediction:
            raise PredictionNotFoundError(prediction_id)

        existing = (
            self.db.query(AnalystReview)
            .filter_by(prediction_id=prediction_id)
            .order_by(AnalystReview.created_at.desc())
            .first()
        )
        if existing and existing.human_decision == decision and existing.analyst == analyst:
            return existing  # idempotent re-submit

        model: Optional[ModelRecord] = self.db.get(ModelRecord, prediction.model_id)
        audit: Optional[AuditRecord] = (
            self.db.query(AuditRecord).filter_by(prediction_id=prediction_id).first()
        )

        review = AnalystReview(
            prediction_id=prediction_id,
            model_id=prediction.model_id,
            model_version=model.version if model else None,
            model_predicted_class=prediction.predicted_class,
            human_decision=decision,
            analyst=str(analyst).strip(),
            notes=notes,
            audit_record_id=audit.id if audit else None,
        )
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        logger.info(
            "Analyst review recorded: prediction=%s decision=%s analyst=%s",
            prediction_id, decision, review.analyst,
        )
        return review

    def list_reviews(
        self,
        prediction_id: Optional[str] = None,
        decision: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Reviews joined with their explanation, newest first."""
        query = self.db.query(AnalystReview)
        if prediction_id:
            query = query.filter_by(prediction_id=prediction_id)
        if decision:
            if decision not in DECISIONS:
                raise ValueError(f"decision must be one of {', '.join(DECISIONS)}.")
            query = query.filter_by(human_decision=decision)
        reviews = query.order_by(AnalystReview.created_at.desc()).limit(limit).all()

        out: List[Dict[str, Any]] = []
        for r in reviews:
            explanation = (
                self.db.query(Explanation).filter_by(prediction_id=r.prediction_id).first()
            )
            out.append(self._serialize(r, explanation))
        return out

    def disagreement_stats(self) -> Dict[str, Any]:
        """How often does human review disagree with the model?"""
        total = self.db.query(AnalystReview).count()
        rejected = (
            self.db.query(AnalystReview).filter_by(human_decision="rejected").count()
        )
        by_analyst: Dict[str, Dict[str, int]] = {}
        for r in self.db.query(AnalystReview).all():
            bucket = by_analyst.setdefault(
                r.analyst, {"total": 0, "rejected": 0, "confirmed": 0}
            )
            bucket["total"] += 1
            bucket[r.human_decision] += 1
        for bucket in by_analyst.values():
            bucket["disagreement_rate"] = (
                round(bucket["rejected"] / bucket["total"], 4) if bucket["total"] else 0.0
            )
        return {
            "total_reviews": total,
            "confirmed": total - rejected,
            "rejected": rejected,
            "disagreement_rate": round(rejected / total, 4) if total else 0.0,
            "by_analyst": by_analyst,
            "interpretation": (
                "Share of reviewed predictions the analyst rejected — the measured "
                "rate at which human review disagrees with the model."
                if total else "No reviews recorded yet."
            ),
        }

    @staticmethod
    def _serialize(review: AnalystReview, explanation: Optional[Explanation]) -> Dict[str, Any]:
        prediction_features = None
        probabilities = None
        pred = review.prediction if hasattr(review, "prediction") else None
        if pred is not None:
            probabilities = pred.probabilities
        return {
            "id": review.id,
            "prediction_id": review.prediction_id,
            "model_id": review.model_id,
            "model_version": review.model_version,
            "model_predicted_class": review.model_predicted_class,
            "human_decision": review.human_decision,
            "disagrees_with_model": review.human_decision == "rejected",
            "analyst": review.analyst,
            "notes": review.notes,
            "audit_record_id": review.audit_record_id,
            "explanation": (
                {
                    "method": explanation.method,
                    "stability_score": explanation.stability_score,
                    "top_features": [
                        f.get("feature") for f in explanation.top_features[:3]
                    ],
                }
                if explanation else None
            ),
            "probabilities": probabilities,
            "created_at": str(review.created_at),
        }
