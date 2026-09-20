"""Model Repository — CRUD layer for ModelRecord entities."""
from __future__ import annotations

from typing import List, Optional
from sqlalchemy.orm import Session

from backend.app.db.models import ModelRecord


class ModelRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        name: str,
        version: str,
        artifact_path: str,
        preprocessing_path: str,
        metrics_json: str = "{}",
        feature_schema_json: str = "[]",
        experiment_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> ModelRecord:
        """Create and persist a ModelRecord."""
        kwargs = {
            "name": name,
            "version": version,
            "artifact_path": str(artifact_path),
            "preprocessing_path": str(preprocessing_path),
            "metrics_json": metrics_json,
            "feature_schema_json": feature_schema_json,
            "experiment_id": experiment_id,
        }
        if model_id:
            kwargs["id"] = model_id
        db_obj = ModelRecord(**kwargs)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get_by_id(self, model_id: str) -> Optional[ModelRecord]:
        """Fetch a model by its UUID."""
        return self.db.query(ModelRecord).filter(ModelRecord.id == model_id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelRecord]:
        """List models with pagination, ordered newest first."""
        return (
            self.db.query(ModelRecord)
            .order_by(ModelRecord.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self) -> int:
        """Return total count of models."""
        return self.db.query(ModelRecord).count()

    def get_by_experiment(self, experiment_id: str) -> List[ModelRecord]:
        """Fetch all models belonging to an experiment."""
        return (
            self.db.query(ModelRecord)
            .filter(ModelRecord.experiment_id == experiment_id)
            .order_by(ModelRecord.created_at.desc())
            .all()
        )

    def delete(self, model_id: str) -> bool:
        """Delete a model by its UUID. Returns True if deleted, False otherwise."""
        obj = self.get_by_id(model_id)
        if not obj:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True
