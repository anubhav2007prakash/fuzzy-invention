"""Previous-hash linkage, chain construction, and chain verification.

Reference implementation of ``backend.app.cryptography.hash_chain``.
Pure, deterministic functions built on ``canonicalize`` and the SHA-256 digest
helpers.  The chain is forward-linked: each record's hash covers the previous
record's hash plus this record's own payload hash.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from backend.app.cryptography.reference.canonical import canonicalize
from backend.app.cryptography.reference.digest import sha256_hex

__all__ = [
    "GENESIS",
    "payload_hash",
    "record_hash",
    "build_chain",
    "verify_record",
    "verify_chain",
]

# Genesis previous hash: 64 zero hex characters.
GENESIS = "0" * 64


def payload_hash(payload: Dict[str, Any]) -> str:
    """SHA-256 of the canonical representation of a payload."""
    return sha256_hex(canonicalize(payload))


def record_hash(previous_hash: str, payload_hash_value: str) -> str:
    """Forward-linked record hash: SHA-256(previous_hash + payload_hash)."""
    return sha256_hex(previous_hash + payload_hash_value)


def build_chain(payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Construct a full chain from a list of payloads in order.

    Returns one dictionary per record:
        {
            "sequence_number": int,
            "payload_json": str,        # canonical JSON of the payload
            "previous_hash": str,
            "payload_hash": str,
            "record_hash": str,
            "timestamp": str,           # ISO-8601 UTC
        }

    The first record links to the genesis previous hash (64 zeros).
    """
    chain: List[Dict[str, Any]] = []
    previous_hash = GENESIS

    for index, payload in enumerate(payloads, start=1):
        canonical_payload = canonicalize(payload)
        payload_hash_value = payload_hash(payload)
        record_hash_value = record_hash(previous_hash, payload_hash_value)

        chain.append(
            {
                "sequence_number": index,
                "payload_json": canonical_payload,
                "previous_hash": previous_hash,
                "payload_hash": payload_hash_value,
                "record_hash": record_hash_value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        previous_hash = record_hash_value

    return chain


def verify_record(record: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Recompute the record hash for a single record.  Returns (ok, errors).

    The production chain stores only ``record_hash`` (the payload hash is not
    stored), so the reference verifier recomputes the payload hash from the
    stored ``payload_json`` and checks that the record's record_hash covers the
    previous-hash pointer plus that payload hash.

    A tampered payload changes the recomputed payload hash, which changes the
    expected record hash, so a record whose stored record_hash does not match
    that recomputed value is reported as a mismatch.
    """
    errors: List[str] = []
    expected_payload_hash = payload_hash(json.loads(record["payload_json"]))
    expected_record_hash = record_hash(record["previous_hash"], expected_payload_hash)

    if record.get("record_hash") != expected_record_hash:
        errors.append(
            f"record_hash mismatch: expected {expected_record_hash}, "
            f"got {record.get('record_hash')}"
        )

    return (len(errors) == 0), errors


def verify_chain(records: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Full chain verification from genesis.

    Records are verified in sequence-number order.  Any broken sequence, wrong
    previous_hash pointer, modified payload, or wrong record_hash produces an
    error.
    """
    sorted_records = sorted(records, key=lambda r: r["sequence_number"])
    errors: List[str] = []
    expected_previous_hash = GENESIS

    for index, record in enumerate(sorted_records):
        sequence_number = record["sequence_number"]

        # Sequence continuity check.
        if index > 0 and sequence_number != sorted_records[index - 1]["sequence_number"] + 1:
            errors.append(
                f"sequence gap at {sequence_number}: expected "
                f"{sorted_records[index - 1]['sequence_number'] + 1}"
            )
            continue

        # Previous-hash pointer check.
        if record["previous_hash"] != expected_previous_hash:
            errors.append(
                f"previous_hash mismatch at sequence {sequence_number}: "
                f"expected {expected_previous_hash}, got {record['previous_hash']}"
            )

        # Payload and record hash recomputation.
        _, record_errors = verify_record(record)
        errors.extend(record_errors)

        # Advance the expected previous hash using the stored record hash.
        expected_previous_hash = record.get("record_hash", "")

    return (len(errors) == 0), errors
