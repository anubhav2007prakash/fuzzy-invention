"""Experiment endpoints — stub for Phase 2."""
from fastapi import APIRouter
router = APIRouter()

@router.get("", summary="List experiments")
def list_experiments():
    return {"experiments": [], "total": 0}
