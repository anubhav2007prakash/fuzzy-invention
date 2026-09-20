"""Audit Pydantic Schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class AuditRecordResponse(BaseModel):
    id: str
    sequence_number: int
    prediction_id: str
    payload_json: str
    previous_hash: str
    record_hash: str
    created_at: datetime

    class Config:
        from_attributes = True

class AuditVerificationRequest(BaseModel):
    verify_entire_chain: bool = True
    start_sequence: Optional[int] = 1
    end_sequence: Optional[int] = None

class AuditVerificationResponse(BaseModel):
    verified: bool
    checked_records: int
    failed_records: List[Dict[str, Any]] = Field(default_factory=list)
    tamper_detected: bool = False
    verification_duration_ms: float = 0.0
    message: str
