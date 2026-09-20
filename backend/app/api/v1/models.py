"""Model management endpoints — stub for Phase 2."""
from fastapi import APIRouter
router = APIRouter()

@router.get("", summary="List trained models")
def list_models():
    return {"models": [], "total": 0}
