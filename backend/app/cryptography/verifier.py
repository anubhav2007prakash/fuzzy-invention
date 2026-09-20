"""Independent Ledger Integrity and Tamper Detection Verifier."""
import json
import time
from typing import List, Dict, Any
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hashing import sha256_hash
from backend.app.cryptography.hash_chain import calculate_record_hash, GENESIS_PREVIOUS_HASH

class VerificationResult:
    def __init__(self, verified: bool, checked_count: int, failed_records: List[Dict[str, Any]], duration_ms: float, message: str):
        self.verified = verified
        self.checked_count = checked_count
        self.failed_records = failed_records
        self.duration_ms = duration_ms
        self.message = message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verified": self.verified,
            "checked_records": self.checked_count,
            "failed_records": self.failed_records,
            "tamper_detected": not self.verified,
            "verification_duration_ms": round(self.duration_ms, 2),
            "message": self.message
        }

def verify_ledger(records: List[Any]) -> VerificationResult:
    """
    Verify the integrity of a sequence of audit records.
    Each record must have: sequence_number, payload_json, previous_hash, record_hash.
    """
    start_time = time.perf_counter()
    if not records:
        return VerificationResult(
            verified=True,
            checked_count=0,
            failed_records=[],
            duration_ms=0.0,
            message="Audit ledger is empty. No records to verify."
        )

    # Sort records strictly by sequence_number ascending
    sorted_records = sorted(records, key=lambda r: r.sequence_number)
    failed_records = []
    expected_previous_hash = GENESIS_PREVIOUS_HASH

    for i, record in enumerate(sorted_records):
        seq = record.sequence_number
        stored_payload_str = record.payload_json
        stored_prev_hash = record.previous_hash
        stored_rec_hash = record.record_hash

        # 1. Verify sequence order continuity
        if i > 0 and seq != sorted_records[i - 1].sequence_number + 1:
            failed_records.append({
                "sequence_number": seq,
                "record_id": getattr(record, "id", str(seq)),
                "error_type": "BROKEN_SEQUENCE",
                "reason": f"Expected sequence {sorted_records[i-1].sequence_number + 1}, found {seq}."
            })

        # 2. Verify previous hash pointer matches preceding record hash
        if stored_prev_hash != expected_previous_hash:
            failed_records.append({
                "sequence_number": seq,
                "record_id": getattr(record, "id", str(seq)),
                "error_type": "PREVIOUS_HASH_MISMATCH",
                "expected": expected_previous_hash,
                "actual": stored_prev_hash,
                "reason": "Previous hash pointer does not match preceding record hash."
            })

        # 3. Parse and re-canonicalize payload to verify payload integrity
        try:
            payload_obj = json.loads(stored_payload_str)
            recomputed_canonical = canonicalize(payload_obj)
            recomputed_payload_hash = sha256_hash(recomputed_canonical)
        except Exception as e:
            failed_records.append({
                "sequence_number": seq,
                "record_id": getattr(record, "id", str(seq)),
                "error_type": "CORRUPTED_JSON_PAYLOAD",
                "reason": f"Invalid JSON payload: {str(e)}"
            })
            expected_previous_hash = stored_rec_hash
            continue

        # 4. Recompute record hash and verify against stored record hash
        recomputed_rec_hash = calculate_record_hash(stored_prev_hash, recomputed_payload_hash)
        if recomputed_rec_hash != stored_rec_hash:
            failed_records.append({
                "sequence_number": seq,
                "record_id": getattr(record, "id", str(seq)),
                "error_type": "TAMPERED_RECORD_HASH",
                "expected_hash": recomputed_rec_hash,
                "stored_hash": stored_rec_hash,
                "reason": "Computed record hash does not match stored record hash. Payload has been modified."
            })

        # Forward pointer for next iteration
        expected_previous_hash = stored_rec_hash

    duration_ms = (time.perf_counter() - start_time) * 1000.0
    is_valid = len(failed_records) == 0

    msg = (
        f"Ledger verified successfully. All {len(sorted_records)} checked records matched their stored hashes and chain links."
        if is_valid
        else f"Verification failed. {len(failed_records)} anomaly(ies) detected in audit ledger."
    )

    return VerificationResult(
        verified=is_valid,
        checked_count=len(sorted_records),
        failed_records=failed_records,
        duration_ms=duration_ms,
        message=msg
    )
