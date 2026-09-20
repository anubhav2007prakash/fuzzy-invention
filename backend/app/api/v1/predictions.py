"""Prediction endpoints — stub for Phase 3."""
from fastapi import APIRouter
router = APIRouter()

@router.get("", summary="List predictions")
def list_predictions():
    return {"predictions": [], "total": 0}
