"""Explanation Repository — CRUD operations for SHAP Explanation records."""
from __future__ import annotations

from typing import List, Optional
from sqlalchemy.orm import Session

from backend.app.db.models import Explanation


class ExplanationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        prediction_id: str,
        method: str = "SHAP",
        top_features_json: str = "[]",
        base_value: Optional[float] = None,
        explanation_version: str = "v1.0",
        stability_score: Optional[float] = None,
        explanation_id: Optional[str] = None,
    ) -> Explanation:
        """Create and persist an Explanation record."""
        kwargs = {
            "prediction_id": prediction_id,
            "method": method,
            "top_features_json": top_features_json,
            "base_value": base_value,
            "explanation_version": explanation_version,
            "stability_score": stability_score,
        }
        if explanation_id:
            kwargs["id"] = explanation_id
        db_obj = Explanation(**kwargs)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get_by_id(self, explanation_id: str) -> Optional[Explanation]:
        """Fetch explanation by primary key."""
        return self.db.query(Explanation).filter(Explanation.id == explanation_id).first()

    def get_by_prediction_id(self, prediction_id: str) -> Optional[Explanation]:
        """Fetch explanation linked to a specific prediction."""
        return self.db.query(Explanation).filter(Explanation.prediction_id == prediction_id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Explanation]:
        """List explanations with pagination, ordered newest first."""
        return (
            self.db.query(Explanation)
            .order_by(Explanation.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self) -> int:
        """Return total number of explanations."""
        return self.db.query(Explanation).count()

    def delete(self, explanation_id: str) -> bool:
        """Delete explanation by ID."""
        obj = self.get_by_id(explanation_id)
        if not obj:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True
