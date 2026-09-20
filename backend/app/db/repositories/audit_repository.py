"""Audit Repository — Database access layer for cryptographic audit records."""
from __future__ import annotations

from typing import List, Optional
from sqlalchemy.orm import Session

from backend.app.db.models import AuditRecord


class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_last_record(self) -> Optional[AuditRecord]:
        """Fetch the latest record in the hash chain (highest sequence_number)."""
        return self.db.query(AuditRecord).order_by(AuditRecord.sequence_number.desc()).first()

    def create_record(
        self,
        sequence_number: int,
        prediction_id: str,
        payload_json: str,
        previous_hash: str,
        record_hash: str,
        record_id: Optional[str] = None,
    ) -> AuditRecord:
        """Append a new verified record to the cryptographic audit chain."""
        kwargs = {
            "sequence_number": sequence_number,
            "prediction_id": prediction_id,
            "payload_json": payload_json,
            "previous_hash": previous_hash,
            "record_hash": record_hash,
        }
        if record_id:
            kwargs["id"] = record_id
        db_obj = AuditRecord(**kwargs)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get_by_id(self, record_id: str) -> Optional[AuditRecord]:
        """Fetch record by primary key."""
        return self.db.query(AuditRecord).filter(AuditRecord.id == record_id).first()

    def get_by_prediction_id(self, prediction_id: str) -> Optional[AuditRecord]:
        """Fetch audit record associated with a prediction."""
        return self.db.query(AuditRecord).filter(AuditRecord.prediction_id == prediction_id).first()

    def get_by_sequence(self, sequence_number: int) -> Optional[AuditRecord]:
        """Fetch record by its sequence position in the chain."""
        return self.db.query(AuditRecord).filter(AuditRecord.sequence_number == sequence_number).first()

    def get_chain(
        self,
        start_seq: int = 1,
        end_seq: Optional[int] = None,
    ) -> List[AuditRecord]:
        """Fetch a slice or the entirety of the audit ledger in strict ascending sequence order."""
        query = self.db.query(AuditRecord).filter(AuditRecord.sequence_number >= start_seq)
        if end_seq is not None:
            query = query.filter(AuditRecord.sequence_number <= end_seq)
        return query.order_by(AuditRecord.sequence_number.asc()).all()

    def count(self) -> int:
        """Total records in the ledger."""
        return self.db.query(AuditRecord).count()
