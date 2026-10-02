"""Single-record and full-ledger verification helpers.

Reference implementation of the production ``verify_ledger`` flow, exposed here
as a small pure verifier over plain dictionaries.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from backend.app.cryptography.reference.chain import GENESIS, payload_hash, record_hash

__all__ = ["verify_ledger", "verify_record"]


def verify_record(record: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Recompute hashes for one record and return (ok, errors)."""
    from backend.app.cryptography.reference.chain import verify_record as _vr

    return _vr(record)


def verify_ledger(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Verify a ledger of records (dicts with sequence_number, payload_json,
    previous_hash, record_hash).  Returns a plain-dict report mirroring the
    production :class:`VerificationResult`::

        {
            "verified": bool,
            "checked_count": int,
            "failed_records": [{"sequence_number", "error_type", ...}],
            "message": str,
        }

    This is a reference-only helper so the differential suite can compare the
    production ORM-backed verifier against an independent implementation.

    Contract aligned with production ``verify_ledger``:
    - records are sorted by ``sequence_number`` ascending (production does this);
    - a broken sequence number gap is NOT a hard failure in the reference
      verifier (production also does not hard-fail on gaps — it checks the
      previous-hash pointer and the record hash only);
    - the previous-hash pointer must match the preceding record's stored
      ``record_hash``;
    - the record hash must equal SHA-256(previous_hash + payload_hash);
    - the pointer advances to the stored ``record_hash`` for every record.
    """
    errors: List[Dict[str, Any]] = []
    expected_previous_hash = GENESIS
    checked_count = 0

    sorted_records = sorted(records, key=lambda r: r["sequence_number"])
    for record in sorted_records:
        sequence_number = record["sequence_number"]

        # Production checks the previous-hash pointer, not sequence contiguity.
        if record["previous_hash"] != expected_previous_hash:
            errors.append(
                {
                    "sequence_number": sequence_number,
                    "error_type": "PREVIOUS_HASH_MISMATCH",
                    "expected": expected_previous_hash,
                    "actual": record["previous_hash"],
                    "reason": "Previous hash pointer does not match preceding record hash.",
                }
            )

        try:
            payload_obj = json.loads(record["payload_json"])
            recomputed_payload_hash = payload_hash(payload_obj)
        except Exception as exc:
            errors.append(
                {
                    "sequence_number": sequence_number,
                    "error_type": "CORRUPTED_JSON_PAYLOAD",
                    "reason": f"Invalid or non-canonical payload: {exc}",
                }
            )
            # Advance the pointer regardless (production does).
            expected_previous_hash = record["record_hash"]
            checked_count += 1
            continue

        recomputed_record_hash = record_hash(record["previous_hash"], recomputed_payload_hash)
        if recomputed_record_hash != record["record_hash"]:
            errors.append(
                {
                    "sequence_number": sequence_number,
                    "error_type": "TAMPERED_RECORD_HASH",
                    "expected_hash": recomputed_record_hash,
                    "stored_hash": record["record_hash"],
                    "reason": "Computed record hash does not match stored record hash. Payload has been modified.",
                }
            )

        # Advance the pointer to the stored record hash (production does this
        # even when the stored hash is wrong).
        expected_previous_hash = record["record_hash"]
        checked_count += 1

    verified = len(errors) == 0
    message = (
        f"Ledger verified successfully. All {checked_count} checked records matched "
        "their stored hashes and chain links."
        if verified
        else f"Verification failed. {len(errors)} anomaly(ies) detected in audit ledger."
    )

    return {
        "verified": verified,
        "checked_count": checked_count,
        "failed_records": errors,
        "message": message,
    }
