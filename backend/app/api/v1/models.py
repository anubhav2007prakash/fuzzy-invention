"""Model management endpoints for SentinelCrypt AI."""
from __future__ import annotations

import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    DatasetNotFoundError,
    ModelNotFoundError,
    ModelTrainingError,
    validate_uuid_format,
)
from backend.app.db.database import get_db
from backend.app.schemas.model import (
    ModelMetricsResponse,
    ModelResponse,
    ModelTrainRequest,
)
from backend.app.services.training_service import TrainingService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/train",
    response_model=ModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Train and evaluate a new detection model",
)
def train_model(
    payload: ModelTrainRequest,
    db: Session = Depends(get_db),
) -> ModelResponse:
    """Trigger end-to-end model training on a registered dataset."""
    service = TrainingService(db)
    try:
        return service.train_model(payload)
    except DatasetNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ModelTrainingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Model training failed unexpectedly")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model training encountered an unexpected error.",
        )


@router.get(
    "",
    summary="List all trained models",
    response_model=Dict[str, Any],
)
def list_models(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(100, ge=1, le=500, description="Limit"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return paginated list of trained models."""
    service = TrainingService(db)
    models = service.list_models(skip=skip, limit=limit)
    total = service.count_models()
    return {
        "models": [m.model_dump() for m in models],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get(
    "/{model_id}",
    response_model=ModelResponse,
    summary="Get model details by ID",
)
def get_model(
    model_id: str,
    db: Session = Depends(get_db),
) -> ModelResponse:
    """Fetch model metadata and high-level evaluation metrics."""
    validate_uuid_format(model_id, "model")
    service = TrainingService(db)
    try:
        return service.get_model(model_id)
    except ModelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{model_id}/metrics",
    response_model=ModelMetricsResponse,
    summary="Get comprehensive evaluation metrics and confusion matrix",
)
def get_model_metrics(
    model_id: str,
    db: Session = Depends(get_db),
) -> ModelMetricsResponse:
    """Fetch full evaluation breakdown including confusion matrix and per-class reports."""
    validate_uuid_format(model_id, "model")
    service = TrainingService(db)
    try:
        return service.get_model_metrics(model_id)
    except ModelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/{model_id}",
    summary="Delete a trained model and its disk artifacts",
)
def delete_model(
    model_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Remove a model and clean up its saved artifacts."""
    validate_uuid_format(model_id, "model")
    service = TrainingService(db)
    try:
        service.delete_model(model_id)
        return {"deleted": True, "id": model_id}
    except ModelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
