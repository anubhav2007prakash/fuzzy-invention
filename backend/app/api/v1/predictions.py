"""Prediction endpoints for SentinelCrypt AI."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    ModelNotFoundError,
    PredictionFailedError,
    PredictionNotFoundError,
    validate_uuid_format,
)
from backend.app.db.database import get_db

logger = logging.getLogger(__name__)
from backend.app.schemas.prediction import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    PredictionRequest,
    PredictionResponse,
)
from backend.app.services.prediction_service import PredictionService

router = APIRouter()


@router.post(
    "",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute inference on a single network traffic flow sample",
)
def create_prediction(
    payload: PredictionRequest,
    db: Session = Depends(get_db),
) -> PredictionResponse:
    """Classify a single network flow sample, construct canonical evidence, and anchor into the cryptographic audit ledger."""
    service = PredictionService(db)
    try:
        return service.predict(payload)
    except ModelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PredictionFailedError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Prediction failed unexpectedly")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inference execution failed.",
        )


@router.post(
    "/batch",
    response_model=BatchPredictionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute vectorized batch inference on multiple network flow samples",
)
def create_batch_predictions(
    payload: BatchPredictionRequest,
    db: Session = Depends(get_db),
) -> BatchPredictionResponse:
    """Execute vectorized batch classification and sequentially anchor each inference into the cryptographic audit chain."""
    service = PredictionService(db)
    try:
        return service.predict_batch(payload)
    except ModelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PredictionFailedError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Batch prediction failed unexpectedly")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch inference execution failed.",
        )


@router.get(
    "",
    summary="List stored predictions with pagination",
    response_model=Dict[str, Any],
)
def list_predictions(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(100, ge=1, le=500, description="Limit"),
    model_id: Optional[str] = Query(None, description="Filter by model ID"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve historical prediction records."""
    service = PredictionService(db)
    return service.list_predictions(skip=skip, limit=limit, model_id=model_id)


@router.get(
    "/{prediction_id}",
    response_model=PredictionResponse,
    summary="Get prediction by ID",
)
def get_prediction(
    prediction_id: str,
    db: Session = Depends(get_db),
) -> PredictionResponse:
    """Fetch details of a specific prediction record."""
    validate_uuid_format(prediction_id, "prediction")
    service = PredictionService(db)
    try:
        return service.get_prediction(prediction_id)
    except PredictionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
