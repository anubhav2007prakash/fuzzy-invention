"""Dataset Pydantic Schemas — request and response models."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class DatasetFeatureSchema(BaseModel):
    id: Optional[int] = None
    feature_name: str
    data_type: str           # "numeric" | "categorical"
    is_selected: bool = True
    missing_count: int = 0

    model_config = {"from_attributes": True}


class DatasetBase(BaseModel):
    name: str
    source: Optional[str] = None
    file_name: str
    file_hash: str           # SHA-256 of raw file bytes
    row_count: int = 0
    feature_count: int = 0
    target_column: str = "label"
    validation_status: str = "VALID"
    label_distribution: Optional[str] = None  # JSON string stored as Text


class DatasetCreate(DatasetBase):
    pass


class DatasetResponse(DatasetBase):
    id: str
    created_at: datetime
    features: List[DatasetFeatureSchema] = Field(default_factory=list)

    # Expose label_distribution as a parsed dict for API consumers
    label_distribution_parsed: Optional[Dict[str, Any]] = Field(None, alias="label_distribution_dict")

    @model_validator(mode="after")
    def parse_label_distribution(self) -> "DatasetResponse":
        if self.label_distribution:
            try:
                object.__setattr__(
                    self,
                    "label_distribution_parsed",
                    json.loads(self.label_distribution),
                )
            except Exception:
                pass
        return self

    model_config = {"from_attributes": True, "populate_by_name": True}


class DatasetListResponse(BaseModel):
    total: int
    datasets: List[DatasetResponse]


class ValidationSummary(BaseModel):
    """Returned immediately after file upload before DB persistence."""
    valid: bool
    detected_format: str
    row_count: int
    feature_count: int
    target_column: str
    label_distribution: Dict[str, int]
    missing_value_summary: Dict[str, int]
    warnings: List[str]
    errors: List[str]
