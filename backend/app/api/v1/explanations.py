"""Explanation endpoints — stub for Phase 4."""
from fastapi import APIRouter
router = APIRouter()

@router.get("", summary="List SHAP explanations")
def list_explanations():
    return {"explanations": [], "total": 0}
