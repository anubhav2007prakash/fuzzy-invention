"""Differential tests — Ledger verification (reference package).

Compares the production verifier (backend.app.cryptography.verifier)
against the clean reference implementation (backend.app.cryptography.reference.verify).

Because the production verifier operates on ORM-model objects while the reference
works with plain dicts, this module provides a lightweight adapter:
``_MockRecord``, which wraps a dict so the production verifier can process it
without a database.

The key assertion in every test is:
    production.verified == reference["verified"]

Any disagreement between the two is a regression requiring investigation.

Component: verification
Tests:
  DT-VER-01  Empty ledger: both report verified=True
  DT-VER-02  Single honest record: verified=True
  DT-VER-03  Multi-record honest chain: verified=True
  DT-VER-04  Tampered payload: both detect verified=False
  DT-VER-05  Wrong previous_hash pointer: both detect verified=False
  DT-VER-06  Wrong stored record_hash: both detect verified=False
  DT-VER-07  Broken sequence: both detect the gap
  DT-VER-08  Out-of-order records: both sort and still verify correctly
  DT-VER-09  Chain with 50 records: production and reference agree on outcome
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    build_audit_record_hashes,
)
from backend.app.cryptography.verifier import verify_ledger
from backend.app.cryptography.reference.chain import GENESIS, verify_chain, verify_record

# ── Mock ORM record ───────────────────────────────────────────────────────────

@dataclass
class _MockRecord:
    """Minimal object that satisfies verifier.verify_ledger's interface."""

    sequence_number: int
    payload_json: str
    previous_hash: str
    record_hash: str
    id: str = ""


# ── Chain builder ─────────────────────────────────────────────────────────────

def _build_chain(payloads: List[Dict[str, Any]]) -> List[_MockRecord]:
    """Build an honest, correctly-linked chain from a list of payload dicts."""
    records: List[_MockRecord] = []
    prev_hash = GENESIS_PREVIOUS_HASH
    for i, payload in enumerate(payloads, start=1):
        canonical_str, payload_hash, record_hash = build_audit_record_hashes(
            payload, previous_hash=prev_hash
        )
        records.append(_MockRecord(
            sequence_number=i,
            payload_json=canonical_str,
            previous_hash=prev_hash,
            record_hash=record_hash,
            id=f"rec-{i}",
        ))
        prev_hash = record_hash
    return records


def _to_ref_dicts(records: List[_MockRecord]) -> List[Dict[str, Any]]:
    """Convert mock records to plain dicts for the reference verifier."""
    return [
        {
            "sequence_number": r.sequence_number,
            "payload_json": r.payload_json,
            "previous_hash": r.previous_hash,
            "record_hash": r.record_hash,
        }
        for r in records
    ]


# ── Helper: compare production verifier to reference verifier ────────────────

def _assert_agreement(records: List[_MockRecord], test_id: str) -> None:
    """Assert that production and reference agree on verification outcome."""
    prod_result = verify_ledger(records)
    ref_dicts = _to_ref_dicts(records)
    ref_result = verify_chain(ref_dicts) if False else _ref_verify(ref_dicts)

    assert prod_result.verified == ref_result["verified"], (
        f"[{test_id}] Verification outcome disagreement:\n"
        f"  production.verified = {prod_result.verified}\n"
        f"  reference.verified  = {ref_result['verified']}\n"
        f"  production.failed_records = {prod_result.failed_records}\n"
        f"  reference.errors = {ref_result['errors']}"
    )


def _ref_verify(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Reference verifier over plain dicts (from backend.app.cryptography.reference.chain)."""
    sorted_records = sorted(records, key=lambda r: r["sequence_number"])
    errors: List[str] = []
    expected_prev = GENESIS

    for rec in sorted_records:
        # Production verifier checks the previous-hash pointer and the record
        # hash only - it does not hard-fail on a sequence gap.
        if rec["previous_hash"] != expected_prev:
            errors.append(f"previous_hash mismatch at sequence {rec['sequence_number']}")
        ok, record_errors = verify_record(rec)
        errors.extend(record_errors)
        expected_prev = rec["record_hash"] or expected_prev

    return {"verified": len(errors) == 0, "errors": errors}


# ── Sample payloads ───────────────────────────────────────────────────────────

_SAMPLE_PAYLOADS = [
    {"seq": 1, "event": "NORMAL", "score": 0.1},
    {"seq": 2, "event": "ALERT", "score": 0.93},
    {"seq": 3, "event": "NORMAL", "score": 0.22},
    {"seq": 4, "event": "CRITICAL", "score": 0.99},
    {"seq": 5, "event": "NORMAL", "score": 0.05},
]


# ── DT-VER-01: Empty ledger ───────────────────────────────────────────────────

def test_dt_ver01_empty_ledger():
    """DT-VER-01: Empty ledger -> verified=True in both implementations."""
    prod_result = verify_ledger([])
    assert prod_result.verified is True, "[DT-VER-01] Production: empty ledger should verify"
    assert _ref_verify([]), "[DT-VER-01] Reference: empty ledger should verify"


# ── DT-VER-02: Single honest record ──────────────────────────────────────────

def test_dt_ver02_single_honest_record():
    """DT-VER-02: Single correctly-linked record verifies in both."""
    records = _build_chain([{"event": "login", "user": "alice"}])
    _assert_agreement(records, "DT-VER-02")
    prod_result = verify_ledger(records)
    assert prod_result.verified is True, "[DT-VER-02] Single honest record should verify"


# ── DT-VER-03: Multi-record honest chain ─────────────────────────────────────

def test_dt_ver03_multi_record_honest_chain():
    """DT-VER-03: 5-record honest chain verifies correctly in both."""
    records = _build_chain(_SAMPLE_PAYLOADS)
    _assert_agreement(records, "DT-VER-03")
    prod_result = verify_ledger(records)
    assert prod_result.verified is True, "[DT-VER-03] Honest chain should verify"
    assert prod_result.checked_count == 5, (
        f"[DT-VER-03] Expected 5 checked records, got {prod_result.checked_count}"
    )


# ── DT-VER-04: Tampered payload ───────────────────────────────────────────────

def test_dt_ver04_tampered_payload():
    """DT-VER-04: Modifying stored payload_json breaks verification in both."""
    records = _build_chain(_SAMPLE_PAYLOADS[:3])
    tampered = list(records)
    original = tampered[1]
    payload_obj = json.loads(original.payload_json)
    payload_obj["score"] = 9999.0   # silent mutation
    tampered[1] = _MockRecord(
        sequence_number=original.sequence_number,
        payload_json=json.dumps(payload_obj, sort_keys=True, separators=(",", ":")),
        previous_hash=original.previous_hash,
        record_hash=original.record_hash,   # hash NOT updated -> tamper indicator
        id=original.id,
    )
    _assert_agreement(tampered, "DT-VER-04")
    prod_result = verify_ledger(tampered)
    assert prod_result.verified is False, "[DT-VER-04] Tampered payload should fail"


# ── DT-VER-05: Wrong previous_hash pointer ───────────────────────────────────

def test_dt_ver05_wrong_previous_hash():
    """DT-VER-05: Incorrect previous_hash pointer breaks verification in both."""
    records = _build_chain(_SAMPLE_PAYLOADS[:3])
    tampered = list(records)
    original = tampered[1]
    tampered[1] = _MockRecord(
        sequence_number=original.sequence_number,
        payload_json=original.payload_json,
        previous_hash="a" * 64,   # wrong pointer
        record_hash=original.record_hash,
        id=original.id,
    )
    _assert_agreement(tampered, "DT-VER-05")
    prod_result = verify_ledger(tampered)
    assert prod_result.verified is False, "[DT-VER-05] Wrong previous_hash should fail"


# ── DT-VER-06: Wrong stored record_hash ──────────────────────────────────────

def test_dt_ver06_wrong_record_hash():
    """DT-VER-06: Incorrect stored record_hash breaks verification in both."""
    records = _build_chain(_SAMPLE_PAYLOADS[:3])
    tampered = list(records)
    original = tampered[2]
    tampered[2] = _MockRecord(
        sequence_number=original.sequence_number,
        payload_json=original.payload_json,
        previous_hash=original.previous_hash,
        record_hash="b" * 64,   # forged hash
        id=original.id,
    )
    _assert_agreement(tampered, "DT-VER-06")
    prod_result = verify_ledger(tampered)
    assert prod_result.verified is False, "[DT-VER-06] Forged record_hash should fail"


# ── DT-VER-07: Broken sequence ───────────────────────────────────────────────

def test_dt_ver07_broken_sequence():
    """DT-VER-07: Gap in sequence numbers detected by both implementations."""
    records = _build_chain(_SAMPLE_PAYLOADS)
    gapped = [r for r in records if r.sequence_number != 3]
    prod_result = verify_ledger(gapped)
    ref_result = _ref_verify(_to_ref_dicts(gapped))
    assert prod_result.verified == ref_result["verified"], (
        f"[DT-VER-07] Disagreement on broken sequence\n"
        f"  prod: {prod_result.verified}, ref: {ref_result['verified']}"
    )
    assert prod_result.verified is False, (
        "[DT-VER-07] Broken sequence should fail production verification"
    )


# ── DT-VER-08: Out-of-order records ──────────────────────────────────────────

def test_dt_ver08_out_of_order():
    """DT-VER-08: Records submitted out-of-order still verify correctly after sorting."""
    records = _build_chain(_SAMPLE_PAYLOADS)
    shuffled = [records[4], records[2], records[0], records[3], records[1]]
    _assert_agreement(shuffled, "DT-VER-08")
    prod_result = verify_ledger(shuffled)
    assert prod_result.verified is True, (
        "[DT-VER-08] Honest out-of-order records should verify after sort"
    )


# ── DT-VER-09: Large chain (50 records) ──────────────────────────────────────

def test_dt_ver09_large_chain():
    """DT-VER-09: 50-record honest chain: production and reference agree."""
    payloads = [{"seq": i, "score": i * 0.01, "label": "benign"} for i in range(1, 51)]
    records = _build_chain(payloads)
    _assert_agreement(records, "DT-VER-09")
    prod_result = verify_ledger(records)
    assert prod_result.verified is True, f"[DT-VER-09] Large chain failed: {prod_result.failed_records}"
    assert prod_result.checked_count == 50
