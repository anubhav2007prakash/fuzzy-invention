"""Crypto reference implementation — deliberately naive, readable reference
implementation of the SentinelCrypt evidence protocol.

DELIBERATELY SIMPLE.  Prioritizes transparency over performance and is used by
differential tests (tests/unit/test_reference_differential.py) to reduce the
risk of a subtle production bug silently changing digests.  DO NOT IMPORT IT
FROM PRODUCTION CODE — it is a test oracle, not an optimized path.

The production protocol (backend/app/cryptography/):
    1. payload   -> canonical JSON  (sorted keys, no whitespace,
                       finite floats use Python JSON encoding, datetime values
                       use datetime.isoformat (naive values are treated as UTC)
    2. payload_hash = SHA-256(canonical_json)
    3. record_hash  = SHA-256( (prev_hash + payload_hash) hex-chars )
    4. chain valid  <=> every record's prev_hash equals the previous record's
                        record_hash (genesis prev = 64 zeros), sequence numbers
                        are contiguous, and both recomputed hashes match.

This file re-implements steps 1-4 from scratch using only hashlib + json.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List


# ── step 1: canonical JSON ────────────────────────────────────────────────────
def ref_canonical_json(value: Any) -> str:
    """Reference canonical serialization.  Mirrors canonicalization.canonicalize.

    Implemented recursively with plain json.dumps only — no sort_keys shortcut —
    so a production regression (e.g. separator, key-order, Unicode, or float
    encoding change) is caught by string comparison instead of shared code.
    """
    if value is None or value is True or value is False:
        return json.dumps(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int,)):
        # bool is a subclass of int — handled above.
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"reference: non-finite float {value!r} is not JSON")
        # json.dumps uses repr (shortest round-trip float) — mirror it so this
        # oracle matches json.dumps-based production exactly.
        return json.dumps(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return json.dumps(value.isoformat(), ensure_ascii=False)
    if isinstance(value, dict):
        items = sorted((str(k), v) for k, v in value.items())
        body = ",".join(
            json.dumps(k, ensure_ascii=False) + ":" + ref_canonical_json(v)
            for k, v in items
        )
        return "{" + body + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(ref_canonical_json(v) for v in value) + "]"
    raise TypeError(f"reference: unsupported type {type(value).__name__}")


# ── steps 2-3: digests ────────────────────────────────────────────────────────
def ref_sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ref_payload_hash(payload: Dict[str, Any]) -> str:
    return ref_sha256_hex(ref_canonical_json(payload))


def ref_record_hash(previous_hash: str, payload_hash: str) -> str:
    return ref_sha256_hex(previous_hash + payload_hash)


GENESIS = "0" * 64


# ── step 4: chain verification ────────────────────────────────────────────────
def ref_verify_chain(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Reference ledger verification over plain dicts (production takes ORM rows).

    Returns {"verified": bool, "errors": [ ... ]} with one entry per problem —
    deliberately chatty so differential tests can localize disagreements.
    """
    errors: List[Dict[str, Any]] = []
    expected_prev = GENESIS
    for i, rec in enumerate(sorted(records, key=lambda r: r["sequence_number"])):
        seq = rec["sequence_number"]
        if i > 0 and seq != records_sorted(records)[i - 1] + 1:
            errors.append({"seq": seq, "type": "sequence_gap"})
        if rec["previous_hash"] != expected_prev:
            errors.append({"seq": seq, "type": "prev_hash_mismatch"})
        recomputed_payload = ref_payload_hash(json.loads(rec["payload_json"]))
        if recomputed_payload != ref_stored_payload_hash(rec):
            errors.append({"seq": seq, "type": "payload_hash_mismatch"})
        recomputed_record = ref_record_hash(rec["previous_hash"], recomputed_payload)
        if recomputed_record != rec["record_hash"]:
            errors.append({"seq": seq, "type": "record_hash_mismatch"})
        expected_prev = rec["record_hash"]
    return {"verified": not errors, "errors": errors}


def records_sorted(records: List[Dict[str, Any]]) -> List[int]:
    return [r["sequence_number"] for r in sorted(records, key=lambda r: r["sequence_number"])]


def ref_stored_payload_hash(rec: Dict[str, Any]) -> str:
    """Payload hash as stored (the production chain stores only record_hash; the
    payload hash is recomputed — reference does the same)."""
    return rec.get("payload_hash") or ref_payload_hash(json.loads(rec["payload_json"]))
