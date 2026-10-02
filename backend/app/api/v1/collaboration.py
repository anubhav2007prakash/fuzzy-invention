"""Collaboration & human-review endpoints (items: HITL, researcher collaboration)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.core.exceptions import PredictionNotFoundError

router = APIRouter()


# ── Human-in-the-loop review ─────────────────────────────────────────────────

@router.post("/reviews", summary="Record an analyst decision on a prediction",
             response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def record_review(spec: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    from backend.app.services.review_service import ReviewService
    service = ReviewService(db)
    try:
        review = service.record_review(
            prediction_id=str(spec.get("prediction_id", "")),
            human_decision=str(spec.get("decision", "")),
            analyst=str(spec.get("analyst", "analyst")),
            notes=spec.get("notes"),
        )
    except PredictionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return service.list_reviews(prediction_id=review.prediction_id, limit=1)[0]


@router.get("/reviews", summary="List analyst reviews (optionally filtered)",
            response_model=Dict[str, Any])
def list_reviews(
    prediction_id: Optional[str] = Query(None),
    decision: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    from backend.app.services.review_service import ReviewService
    service = ReviewService(db)
    try:
        items = service.list_reviews(prediction_id=prediction_id, decision=decision, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"reviews": items, "total": len(items)}


@router.get("/reviews/stats", summary="Model-vs-human disagreement statistics",
            response_model=Dict[str, Any])
def review_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    from backend.app.services.review_service import ReviewService
    return ReviewService(db).disagreement_stats()


# ── Experiment collaboration ─────────────────────────────────────────────────

@router.get("/experiments/{exp_id}/status", summary="Ownership, review, evidence status",
            response_model=Dict[str, Any])
def experiment_status(exp_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    from backend.app.services.collaboration_service import CollaborationService
    return CollaborationService(db).status_view(exp_id)


@router.put("/experiments/{exp_id}/review-state",
            summary="Set owner / review status / approval",
            response_model=Dict[str, Any])
def update_review_state(exp_id: str, spec: Dict[str, Any],
                        db: Session = Depends(get_db)) -> Dict[str, Any]:
    from backend.app.services.collaboration_service import CollaborationService
    service = CollaborationService(db)
    try:
        service.update_state(
            exp_id,
            owner=spec.get("owner"),
            review_status=spec.get("review_status"),
            reviewer=spec.get("reviewer"),
            approve=spec.get("approve"),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return service.status_view(exp_id)


@router.post("/experiments/{exp_id}/comments", summary="Add a comment",
             response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def add_comment(exp_id: str, spec: Dict[str, Any],
                db: Session = Depends(get_db)) -> Dict[str, Any]:
    from backend.app.services.collaboration_service import CollaborationService
    service = CollaborationService(db)
    try:
        service.add_comment(
            experiment_id=exp_id,
            author=str(spec.get("author", "")),
            body=str(spec.get("body", "")),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return service.status_view(exp_id)


@router.get("/experiments/{exp_id}/comments", summary="List comments",
            response_model=Dict[str, Any])
def list_comments(exp_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    from backend.app.services.collaboration_service import CollaborationService
    items = CollaborationService(db).list_comments(exp_id)
    return {"comments": items, "total": len(items)}
