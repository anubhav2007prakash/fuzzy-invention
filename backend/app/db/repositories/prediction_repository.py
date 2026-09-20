"""Prediction Repository — CRUD operations for Prediction records."""
from __future__ import annotations

from typing import List, Optional
from sqlalchemy.orm import Session

from backend.app.db.models import Prediction


class PredictionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        model_id: str,
        input_hash: str,
        predicted_class: str,
        probabilities_json: Optional[str] = None,
        latency_ms: float = 0.0,
        request_source: str = "api",
        prediction_id: Optional[str] = None,
    ) -> Prediction:
        """Create and persist a Prediction record."""
        kwargs = {
            "model_id": model_id,
            "input_hash": input_hash,
            "predicted_class": predicted_class,
            "probabilities_json": probabilities_json,
            "latency_ms": latency_ms,
            "request_source": request_source,
        }
        if prediction_id:
            kwargs["id"] = prediction_id
        db_obj = Prediction(**kwargs)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get_by_id(self, prediction_id: str) -> Optional[Prediction]:
        """Fetch prediction by ID."""
        return self.db.query(Prediction).filter(Prediction.id == prediction_id).first()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        model_id: Optional[str] = None,
    ) -> List[Prediction]:
        """Retrieve paginated predictions, optionally filtered by model_id, ordered newest first."""
        query = self.db.query(Prediction)
        if model_id:
            query = query.filter(Prediction.model_id == model_id)
        return query.order_by(Prediction.created_at.desc()).offset(skip).limit(limit).all()

    def count(self, model_id: Optional[str] = None) -> int:
        """Count total predictions, optionally filtered by model_id."""
        query = self.db.query(Prediction)
        if model_id:
            query = query.filter(Prediction.model_id == model_id)
        return query.count()

    def delete(self, prediction_id: str) -> bool:
        """Delete prediction record by ID."""
        obj = self.get_by_id(prediction_id)
        if not obj:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True
