"""Cryptographic Audit Ledger endpoints for SentinelCrypt AI."""
from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.exceptions import validate_uuid_format
from backend.app.db.database import get_db
from backend.app.schemas.audit import (
    AuditRecordResponse,
    AuditVerificationRequest,
    AuditVerificationResponse,
)
from backend.app.services.audit_service import AuditService

router = APIRouter()


@router.get(
    "/records",
    summary="List audit records in sequential order",
    response_model=Dict[str, Any],
)
def list_records(
    skip: int = Query(0, ge=0, description="Offset (records to skip)"),
    limit: int = Query(100, ge=1, le=500, description="Page limit"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve paginated cryptographic audit records ordered strictly by sequence number."""
    service = AuditService(db)
    records = service.list_audit_records(skip=skip, limit=limit)
    total = service.count()
    return {
        "records": [r.model_dump() for r in records],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get(
    "/records/{record_id}",
    response_model=AuditRecordResponse,
    summary="Get a specific audit record by record ID",
)
def get_record(
    record_id: str,
    db: Session = Depends(get_db),
) -> AuditRecordResponse:
    """Fetch an individual audit record and its canonical evidence payload."""
    validate_uuid_format(record_id, "audit record")
    service = AuditService(db)
    record = service.get_audit_record(record_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit record '{record_id}' not found.",
        )
    return record


@router.get(
    "/predictions/{prediction_id}",
    response_model=AuditRecordResponse,
    summary="Get the audit record anchored to a prediction ID",
)
def get_record_by_prediction(
    prediction_id: str,
    db: Session = Depends(get_db),
) -> AuditRecordResponse:
    """Retrieve the cryptographic audit record linked to a specific inference prediction."""
    validate_uuid_format(prediction_id, "prediction")
    service = AuditService(db)
    record = service.get_audit_record_by_prediction(prediction_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit record found for prediction '{prediction_id}'.",
        )
    return record


@router.get(
    "/status",
    summary="Get ledger status and summary integrity information",
    response_model=Dict[str, Any],
)
def get_status(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return high-level audit ledger health, latest sequence number, latest hash, and integrity check."""
    service = AuditService(db)
    return service.get_ledger_status()


@router.post(
    "/verify",
    response_model=AuditVerificationResponse,
    summary="Mathematically verify ledger chain integrity and detect tampering",
)
def verify_ledger_chain(
    payload: Optional[AuditVerificationRequest] = None,
    db: Session = Depends(get_db),
) -> AuditVerificationResponse:
    """Execute mathematical verification over the stored cryptographic hash chain.

    Validates:
    1. Deterministic canonical JSON payload hashes.
    2. Strict sequence number continuity (no dropped records).
    3. Sequential SHA-256 hash pointer linkage: RecordHash[i] = SHA-256(RecordHash[i-1] + PayloadHash[i]).
    4. Immediate localization of any corrupted sequence number.
    """
    req = payload or AuditVerificationRequest()
    service = AuditService(db)
    start_seq = req.start_sequence or 1
    end_seq = req.end_sequence if not req.verify_entire_chain else None

    return service.verify_ledger_chain(start_sequence=start_seq, end_sequence=end_seq)


@router.get(
    "/export",
    summary="Export audit ledger records as JSON",
)
def export_records(
    format: str = Query("json", description="Export format: json or csv"),
    start_sequence: int = Query(1, ge=1, description="Start sequence number"),
    end_sequence: Optional[int] = Query(None, ge=1, description="End sequence number (None = all)"),
    db: Session = Depends(get_db),
):
    """Export audit records as downloadable JSON or CSV."""
    from fastapi.responses import StreamingResponse
    import csv
    import io
    import json

    service = AuditService(db)
    records = service.list_audit_records(skip=start_sequence - 1, limit=10000)

    # Filter by end_sequence if specified
    if end_sequence is not None:
        records = [r for r in records if r.sequence_number <= end_sequence]

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["sequence_number", "prediction_id", "record_hash",
                         "previous_hash", "created_at"])
        for r in records:
            writer.writerow([r.sequence_number, r.prediction_id, r.record_hash,
                             r.previous_hash, r.created_at])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_ledger.csv"},
        )
    else:
        data = [r.model_dump() for r in records]
        return StreamingResponse(
            iter([json.dumps(data, indent=2, default=str)]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_ledger.json"},
        )
