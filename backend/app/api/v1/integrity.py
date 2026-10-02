"""Database Integrity Audit API endpoint."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.research.integrity_audit import audit_database

router = APIRouter()


@router.post(
    "/database/verify",
    summary="Verify database integrity",
    response_model=Dict[str, Any],
    status_code=200,
)
def verify_database_integrity(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Run a comprehensive database integrity audit.

    Performs read-only checks for:
    - Orphan records (references to non-existent entities)
    - Invalid foreign keys
    - Duplicate primary identifiers
    - Impossible states / status contradictions
    - Missing provenance metadata
    - Missing referenced artifacts (files, models)
    - Inconsistent timestamps
    - Invalid relationships between records

    Does NOT mutate the database. Returns a structured audit report.

    Returns:
        Audit report with issue counts by type and severity, detailed per-table
        findings, overall status, and recommended actions.
    """
    return audit_database(db)