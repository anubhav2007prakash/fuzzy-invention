"""DatasetService — business logic for dataset ingestion and registration."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.exceptions import InvalidDatasetError, DatasetNotFoundError
from backend.app.core.logging import get_logger
from backend.app.cryptography.hashing import sha256_hash
from backend.app.db.models import Dataset
from backend.app.db.repositories.dataset_repository import DatasetRepository
from backend.app.ml.preprocessing.validators import validate_dataset
from backend.app.schemas.dataset import (
    DatasetCreate, DatasetFeatureSchema, DatasetResponse, ValidationSummary,
)

logger = get_logger(__name__)


class DatasetService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DatasetRepository(db)

    # ── Upload & register ─────────────────────────────────────────────────────

    def upload_and_register(
        self,
        file_content: bytes,
        file_name: str,
        dataset_name: Optional[str] = None,
        source: Optional[str] = None,
        custom_target_column: Optional[str] = None,
    ) -> tuple[Dataset, ValidationSummary]:
        """
        1. Compute SHA-256 of raw bytes (deduplication guard).
        2. Validate the CSV.
        3. Save raw file to data/raw/.
        4. Persist dataset metadata and feature schema to DB.
        5. Return (Dataset ORM object, ValidationSummary).
        """
        # 1. Checksum — reject exact duplicates
        file_hash = sha256_hash(file_content)
        existing = self.repo.get_by_file_hash(file_hash)
        if existing:
            logger.info("Duplicate dataset detected (hash=%s). Returning existing record.", file_hash[:16])
            summary = ValidationSummary(
                valid=True,
                detected_format="CACHED",
                row_count=existing.row_count,
                feature_count=existing.feature_count,
                target_column=existing.target_column,
                label_distribution=json.loads(existing.label_distribution or "{}"),
                missing_value_summary={},
                warnings=["This file has already been registered. Returning existing record."],
                errors=[],
            )
            return existing, summary

        # 2. Validate
        logger.info("Validating dataset '%s' (%d bytes).", file_name, len(file_content))
        df, report = validate_dataset(file_content, file_name, custom_target_column)

        # 3. Save raw file
        raw_path = settings.DATA_RAW_DIR / file_name
        raw_path.write_bytes(file_content)
        logger.info("Raw file saved: %s", raw_path)

        # 4. Build ORM create object
        display_name = dataset_name or Path(file_name).stem
        label_dist_json = json.dumps(report.label_distribution)

        obj_in = DatasetCreate(
            name=display_name,
            source=source or "",
            file_name=file_name,
            file_hash=file_hash,
            row_count=report.row_count,
            feature_count=report.feature_count,
            target_column=report.target_column,
            validation_status="VALID" if report.valid else "INVALID",
            label_distribution=label_dist_json,
        )

        # Build feature metadata
        features = [
            DatasetFeatureSchema(
                feature_name=f,
                data_type="categorical" if df[f].dtype == object else "numeric",
                is_selected=True,
                missing_count=int(df[f].isnull().sum()),
            )
            for f in df.columns
            if f != report.target_column
        ]

        dataset = self.repo.create(obj_in, features=features)
        logger.info("Dataset registered: id=%s, rows=%d", dataset.id, report.row_count)

        summary = ValidationSummary(
            valid=report.valid,
            detected_format=report.detected_format,
            row_count=report.row_count,
            feature_count=report.feature_count,
            target_column=report.target_column,
            label_distribution=report.label_distribution,
            missing_value_summary=report.missing_value_counts,
            warnings=report.warnings,
            errors=report.errors,
        )
        return dataset, summary

    # ── Query ─────────────────────────────────────────────────────────────────

    def get_by_id(self, dataset_id: str) -> Dataset:
        dataset = self.repo.get_by_id(dataset_id)
        if not dataset:
            raise DatasetNotFoundError(dataset_id)
        return dataset

    def list_all(self, skip: int = 0, limit: int = 100) -> list[Dataset]:
        return self.repo.get_all(skip=skip, limit=limit)

    def count(self) -> int:
        return self.repo.count()
