"""Audit Service — Business logic for cryptographic ledger anchoring and verification."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    build_audit_record_hashes,
)
from backend.app.cryptography.verifier import VerificationResult, verify_ledger
from backend.app.db.models import AuditRecord
from backend.app.db.repositories.audit_repository import AuditRepository
from backend.app.schemas.audit import AuditRecordResponse, AuditVerificationResponse

logger = get_logger(__name__)


class AuditService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AuditRepository(db)

    def create_audit_entry(
        self,
        prediction_id: str,
        evidence_payload: Dict[str, Any],
    ) -> AuditRecord:
        """Anchor prediction evidence into the immutable forward-linked SHA-256 hash chain."""
        last_record = self.repo.get_last_record()

        if last_record is None:
            previous_hash = GENESIS_PREVIOUS_HASH
            sequence_number = 1
        else:
            previous_hash = last_record.record_hash
            sequence_number = last_record.sequence_number + 1

        canonical_payload, payload_hash, record_hash = build_audit_record_hashes(
            payload=evidence_payload,
            previous_hash=previous_hash,
        )

        record = self.repo.create_record(
            sequence_number=sequence_number,
            prediction_id=prediction_id,
            payload_json=canonical_payload,
            previous_hash=previous_hash,
            record_hash=record_hash,
        )

        logger.info(
            "Anchored audit record: seq=%d, pred_id=%s, record_hash=%s",
            sequence_number,
            prediction_id,
            record_hash[:16],
        )
        return record

    def get_audit_record_by_prediction(self, prediction_id: str) -> Optional[AuditRecordResponse]:
        """Fetch audit record associated with a prediction."""
        record = self.repo.get_by_prediction_id(prediction_id)
        if not record:
            return None
        return AuditRecordResponse.model_validate(record)

    def get_audit_record(self, record_id: str) -> Optional[AuditRecordResponse]:
        """Fetch audit record by ID."""
        record = self.repo.get_by_id(record_id)
        if not record:
            return None
        return AuditRecordResponse.model_validate(record)

    def list_audit_records(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditRecordResponse]:
        """List audit records in sequence order."""
        records = self.repo.get_chain(start_seq=skip + 1, end_seq=skip + limit)
        return [AuditRecordResponse.model_validate(r) for r in records]

    def count(self) -> int:
        """Return total number of audit records."""
        return self.repo.count()

    def verify_ledger_chain(
        self,
        start_sequence: int = 1,
        end_sequence: Optional[int] = None,
    ) -> AuditVerificationResponse:
        """Perform mathematical verification on the stored cryptographic hash chain."""
        records = self.repo.get_chain(start_seq=start_sequence, end_seq=end_sequence)
        result: VerificationResult = verify_ledger(records)
        res_dict = result.to_dict()
        return AuditVerificationResponse(**res_dict)
