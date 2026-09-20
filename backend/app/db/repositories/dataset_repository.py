"""Dataset Repository — CRUD layer for datasets and their feature metadata."""
from __future__ import annotations

import json
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.app.db.models import Dataset, DatasetFeature
from backend.app.schemas.dataset import DatasetCreate, DatasetFeatureSchema


class DatasetRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Create ────────────────────────────────────────────────────────────────

    def create(
        self,
        obj_in: DatasetCreate,
        features: Optional[List[DatasetFeatureSchema]] = None,
    ) -> Dataset:
        db_obj = Dataset(
            name=obj_in.name,
            source=obj_in.source,
            file_name=obj_in.file_name,
            file_hash=obj_in.file_hash,
            row_count=obj_in.row_count,
            feature_count=obj_in.feature_count,
            target_column=obj_in.target_column,
            validation_status=obj_in.validation_status,
            label_distribution=obj_in.label_distribution,
        )
        self.db.add(db_obj)
        self.db.flush()   # get db_obj.id before adding features

        if features:
            for feat in features:
                self.db.add(DatasetFeature(
                    dataset_id=db_obj.id,
                    feature_name=feat.feature_name,
                    data_type=feat.data_type,
                    is_selected=feat.is_selected,
                    missing_count=feat.missing_count,
                ))

        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_by_id(self, dataset_id: str) -> Optional[Dataset]:
        return self.db.query(Dataset).filter(Dataset.id == dataset_id).first()

    def get_by_file_hash(self, file_hash: str) -> Optional[Dataset]:
        return self.db.query(Dataset).filter(Dataset.file_hash == file_hash).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Dataset]:
        return self.db.query(Dataset).order_by(Dataset.created_at.desc()).offset(skip).limit(limit).all()

    def count(self) -> int:
        return self.db.query(Dataset).count()
