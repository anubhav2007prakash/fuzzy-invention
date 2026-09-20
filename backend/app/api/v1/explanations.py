"""Explainability API endpoints for SentinelCrypt AI.

Routes:
    POST   /explain/{prediction_id}            — generate SHAP explanation
    GET    /explain/{prediction_id}            — retrieve stored explanation
    GET    /explain/                           — list all stored explanations
    POST   /explain/stability/{prediction_id}  — run standalone stability analysis

DISCLAIMER (propagated to every response body via ExplanationResponse.limitations):
    SHAP attributions indicate feature importance to the model's decision for a
    specific input.  They are not causal ground-truth explanations.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    ExplanationFailedError,
    ModelNotFoundError,
    PredictionNotFoundError,
)
from backend.app.db.database import get_db
from backend.app.schemas.explanation import (
    ExplainRequest,
    ExplanationResponse,
    StabilityRequest,
)
from backend.app.services.explanation_service import ExplanationService

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# POST /explain/{prediction_id}  — Generate or regenerate explanation
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/{prediction_id}",
    response_model=ExplanationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a SHAP explanation for a stored prediction",
)
def explain_prediction(
    prediction_id: str,
    body: Optional[ExplainRequest] = None,
    db: Session = Depends(get_db),
) -> ExplanationResponse:
    """Compute a SHAP-based feature attribution explanation for an existing prediction.

    If `features` is provided in the request body the service uses them for
    exact SHAP computation.  Otherwise it falls back to a zero-vector input
    which produces valid model-relative attributions.

    **Limitations (returned in every response)**:
    - SHAP attributions reflect the model's decision boundary, not causal ground truth.
    - Stability score measures consistency of attributions under Gaussian perturbation,
      not correctness of explanations.
    """
    req = body or ExplainRequest()
    service = ExplanationService(db)

    try:
        if req.features:
            result = service.explain_features(
                prediction_id=prediction_id,
                raw_features=req.features,
                top_k=req.top_k,
                compute_stability=req.compute_stability,
                noise_std=req.noise_std,
                n_repetitions=req.n_repetitions,
            )
        else:
            result = service.explain_prediction(
                prediction_id=prediction_id,
                top_k=req.top_k,
                compute_stability=req.compute_stability,
                noise_std=req.noise_std,
                n_repetitions=req.n_repetitions,
            )
    except PredictionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (ModelNotFoundError, ExplanationFailedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return result


# ─────────────────────────────────────────────────────────────────────────────
# GET /explain/{prediction_id}   — Retrieve stored explanation
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{prediction_id}",
    response_model=ExplanationResponse,
    summary="Retrieve stored SHAP explanation for a prediction",
)
def get_explanation(
    prediction_id: str,
    db: Session = Depends(get_db),
) -> ExplanationResponse:
    """Fetch the most recently stored SHAP explanation for a given prediction ID."""
    service = ExplanationService(db)
    try:
        return service.get_explanation(prediction_id)
    except PredictionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stored explanation found for prediction '{prediction_id}'.",
        ) from exc


# ─────────────────────────────────────────────────────────────────────────────
# GET /explain/                  — List all explanations
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=Dict[str, Any],
    summary="List all stored SHAP explanations",
)
def list_explanations(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Page limit"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return paginated list of stored explanations ordered newest first."""
    service = ExplanationService(db)
    return service.list_explanations(skip=skip, limit=limit)


# ─────────────────────────────────────────────────────────────────────────────
# POST /explain/stability/{prediction_id}  — Standalone stability analysis
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/stability/{prediction_id}",
    response_model=Dict[str, Any],
    summary="Run standalone explanation stability analysis for a prediction",
)
def compute_stability(
    prediction_id: str,
    body: Optional[StabilityRequest] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Execute explanation stability analysis (EXP-B).

    Applies controlled Gaussian perturbations and measures cosine similarity
    between baseline and perturbed SHAP vectors.

    Returns:
        - stability_score: mean cosine similarity over repetitions (0-1).
        - n_repetitions: number of perturbation rounds used.
        - noise_std: σ of Gaussian noise applied.

    **Limitations**: Stability measures consistency of model attributions
    under perturbation — not correctness or causal validity.
    """
    req = body or StabilityRequest()
    service = ExplanationService(db)

    try:
        if req.features:
            result = service.explain_features(
                prediction_id=prediction_id,
                raw_features=req.features,
                top_k=10,
                compute_stability=True,
                noise_std=req.noise_std,
                n_repetitions=req.n_repetitions,
            )
        else:
            result = service.explain_prediction(
                prediction_id=prediction_id,
                top_k=10,
                compute_stability=True,
                noise_std=req.noise_std,
                n_repetitions=req.n_repetitions,
            )
    except PredictionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (ModelNotFoundError, ExplanationFailedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return {
        "prediction_id": prediction_id,
        "stability_score": result.stability_score,
        "n_repetitions": req.n_repetitions,
        "noise_std": req.noise_std,
        "disclaimer": (
            "Stability measures consistency of model attributions under perturbation. "
            "It does not validate causal correctness of explanations."
        ),
    }
