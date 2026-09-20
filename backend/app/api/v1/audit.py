"""Cryptographic Audit Ledger endpoints — stub for Phase 5."""
from fastapi import APIRouter
router = APIRouter()

@router.get("", summary="List audit records")
def list_audit():
    return {"records": [], "total": 0, "ledger_verified": False}
