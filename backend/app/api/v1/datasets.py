"""Dataset API endpoints — /api/v1/datasets."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.exceptions import InvalidDatasetError, UnsupportedFormatError, DatasetNotFoundError
from backend.app.core.file_security import validate_filename
from backend.app.db.database import get_db
from backend.app.schemas.dataset import DatasetListResponse, DatasetResponse, ValidationSummary
from backend.app.services.dataset_service import DatasetService

router = APIRouter()


def _error_response(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message, "details": {}}}


# ── POST /datasets  ───────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and register a dataset",
    description=(
        "Accepts a CSV file (UNSW-NB15, CICIDS2017, or generic).\n"
        "Validates schema, deduplicates by SHA-256, and persists metadata."
    ),
)
async def upload_dataset(
    file: UploadFile = File(..., description="CSV network-flow dataset file."),
    dataset_name: Optional[str] = Form(None, description="Human-readable display name."),
    source: Optional[str] = Form(None, description="Dataset source / URL reference."),
    target_column: Optional[str] = Form(None, description="Override auto-detected label column name."),
    db: Session = Depends(get_db),
):
    # Size guard
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=_error_response("FILE_TOO_LARGE",
                                   f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB."),
        )

    svc = DatasetService(db)
    try:
        dataset, summary = svc.upload_and_register(
            file_content=content,
            file_name=file.filename or "dataset.csv",
            dataset_name=dataset_name,
            source=source,
            custom_target_column=target_column,
        )
    except UnsupportedFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_error_response(exc.code, exc.message),
        )
    except InvalidDatasetError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_error_response(exc.code, exc.message),
        )

    return {
        "dataset_id": dataset.id,
        "message": "Dataset registered successfully.",
        "validation": summary.model_dump(),
    }


# ── GET /datasets  ────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=DatasetListResponse,
    summary="List all registered datasets",
)
def list_datasets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    svc = DatasetService(db)
    datasets = svc.list_all(skip=skip, limit=limit)
    total = svc.count()
    return DatasetListResponse(
        total=total,
        datasets=[DatasetResponse.model_validate(d) for d in datasets],
    )


# ── GET /datasets/{dataset_id}  ───────────────────────────────────────────────

@router.get(
    "/{dataset_id}",
    response_model=DatasetResponse,
    summary="Retrieve dataset metadata and feature schema",
)
def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
):
    svc = DatasetService(db)
    try:
        dataset = svc.get_by_id(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=_error_response(exc.code, exc.message))
    return DatasetResponse.model_validate(dataset)


# ── GET /datasets/{dataset_id}/preview  ──────────────────────────────────────

@router.get(
    "/{dataset_id}/preview",
    summary="Preview dataset: first 5 rows + column statistics",
)
def preview_dataset(
    dataset_id: str,
    n_rows: int = Query(5, ge=1, le=20, description="Number of rows to preview"),
    db: Session = Depends(get_db),
):
    """Return the first N rows and basic column statistics for a registered dataset."""
    svc = DatasetService(db)
    try:
        dataset = svc.get_by_id(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=_error_response(exc.code, exc.message))

    csv_path = Path(settings.DATA_RAW_DIR) / dataset.file_name
    if not csv_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_response("FILE_NOT_FOUND", "Raw dataset file not found on disk."),
        )

    try:
        df = pd.read_csv(csv_path, nrows=n_rows)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_error_response("READ_ERROR", f"Could not read dataset: {e}"),
        )

    # Build column statistics from the preview
    stats = {}
    for col in df.columns:
        col_stat: dict = {"dtype": str(df[col].dtype), "non_null": int(df[col].count())}
        if pd.api.types.is_numeric_dtype(df[col]):
            col_stat["mean"] = round(float(df[col].mean()), 4)
            col_stat["std"] = round(float(df[col].std()), 4)
            col_stat["min"] = round(float(df[col].min()), 4)
            col_stat["max"] = round(float(df[col].max()), 4)
        else:
            col_stat["unique"] = int(df[col].nunique())
            col_stat["top"] = str(df[col].mode().iloc[0]) if len(df[col].mode()) > 0 else None
        stats[col] = col_stat

    return {
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "preview_rows": df.to_dict(orient="records"),
        "column_stats": stats,
        "total_rows": dataset.row_count,
        "total_features": dataset.feature_count,
    }
