"""Differential tests — Hash-chain construction (reference package).

Compares the production hash-chain module (backend.app.cryptography.hash_chain)
against the clean reference implementation (backend.app.cryptography.reference.chain).

The reference builds payload_hash, record_hash, and the whole chain entirely
independently using only hashlib and Python built-ins, so any production
regression that silently changes hash linkage will be caught.

Protocol semantics being verified:
    payload_hash  = SHA-256(canonical_json(payload))
    record_hash   = SHA-256(previous_hash + payload_hash)
    GENESIS       = "0" * 64
    chain         = payload N links to payload N-1's record_hash
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    build_audit_record_hashes,
    calculate_payload_hash,
    calculate_record_hash,
)
from backend.app.cryptography.reference.chain import (
    GENESIS,
    build_chain,
    payload_hash,
    record_hash,
    verify_chain,
    verify_record,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def ref_canonical_json_for_chain(payload: Dict[str, Any]) -> str:
    """Reference canonical JSON used by the chain differential tests."""
    from backend.app.cryptography.reference.canonical import canonicalize
    return canonicalize(payload)


# ── DT-CHAIN-01: Payload hash matches reference ───────────────────────────────

_PAYLOAD_CASES = [
    {"event": "login", "user": "alice", "severity": 1},
    {"prediction": 0, "score": 0.9876, "features": [1.0, 2.0, 3.0]},
    {"z_key": "z_val", "a_key": "a_val"},                     # key ordering matters
    {"nested": {"inner": {"deep": "value"}}},
    {"ts": datetime(2024, 1, 1, tzinfo=timezone.utc), "label": "genesis"},
    {},                                                         # empty payload
    {"unicode": "こんにちは🔐"},
    {"numbers": [0, -1, 999, 2**32]},
]

@pytest.mark.parametrize("payload", _PAYLOAD_CASES)
def test_dt_chain01_payload_hash(payload):
    """DT-CHAIN-01: calculate_payload_hash matches reference payload hash."""
    prod = calculate_payload_hash(payload)
    ref = payload_hash(payload)
    assert prod == ref, (
        f"[DT-CHAIN-01] Payload hash mismatch for {payload!r}\n"
        f"  production: {prod}\n"
        f"  reference : {ref}"
    )
    assert len(prod) == 64 and all(c in "0123456789abcdef" for c in prod), (
        f"[DT-CHAIN-01] Invalid hash format: {prod!r}"
    )


# ── DT-CHAIN-02: Record hash matches reference ────────────────────────────────

_RECORD_HASH_CASES_VALID = [
    ("0" * 64, "a" * 64),
    ("d" * 64, "e" * 64),
    (GENESIS_PREVIOUS_HASH, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
]

@pytest.mark.parametrize("prev_hash,payload_hash", _RECORD_HASH_CASES_VALID)
def test_dt_chain02_record_hash(prev_hash, payload_hash):
    """DT-CHAIN-02: calculate_record_hash matches reference record hash."""
    prod = calculate_record_hash(prev_hash, payload_hash)
    ref = record_hash(prev_hash, payload_hash)
    assert prod == ref, (
        f"[DT-CHAIN-02] Record hash mismatch\n"
        f"  prev_hash   : {prev_hash}\n"
        f"  payload_hash: {payload_hash}\n"
        f"  production  : {prod}\n"
        f"  reference   : {ref}"
    )


# ── DT-CHAIN-03: Full triple from build_audit_record_hashes ──────────────────

@pytest.mark.parametrize("payload", _PAYLOAD_CASES[:5])  # subset for speed
def test_dt_chain03_full_triple(payload):
    """DT-CHAIN-03: build_audit_record_hashes triple matches reference components."""
    prev_hash = "0" * 64
    canonical_str, prod_payload_hash, prod_record_hash = build_audit_record_hashes(
        payload, previous_hash=prev_hash
    )

    ref_canon = ref_canonical_json_for_chain(payload)
    ref_ph = payload_hash(payload)
    ref_rh = record_hash(prev_hash, ref_ph)

    assert canonical_str == ref_canon, (
        f"[DT-CHAIN-03] Canonical string mismatch\n"
        f"  prod: {canonical_str!r}\n"
        f"  ref : {ref_canon!r}"
    )
    assert prod_payload_hash == ref_ph, (
        f"[DT-CHAIN-03] Payload hash mismatch: prod={prod_payload_hash}, ref={ref_ph}"
    )
    assert prod_record_hash == ref_rh, (
        f"[DT-CHAIN-03] Record hash mismatch: prod={prod_record_hash}, ref={ref_rh}"
    )


# ── DT-CHAIN-04: Genesis record ───────────────────────────────────────────────

def test_dt_chain04_genesis():
    """DT-CHAIN-04: GENESIS_PREVIOUS_HASH constant equals reference GENESIS."""
    assert GENESIS_PREVIOUS_HASH == GENESIS, (
        f"[DT-CHAIN-04] Genesis mismatch: "
        f"production={GENESIS_PREVIOUS_HASH!r}, reference={GENESIS!r}"
    )
    assert GENESIS_PREVIOUS_HASH == "0" * 64, (
        f"[DT-CHAIN-04] Genesis is not 64 zeros: {GENESIS_PREVIOUS_HASH!r}"
    )


# ── DT-CHAIN-05: Multi-record chain linkage ───────────────────────────────────

_CHAIN_PAYLOADS: List[Dict[str, Any]] = [
    {"seq": 1, "event": "NORMAL", "score": 0.1},
    {"seq": 2, "event": "ALERT", "score": 0.93},
    {"seq": 3, "event": "NORMAL", "score": 0.22},
    {"seq": 4, "event": "CRITICAL", "score": 0.99},
    {"seq": 5, "event": "NORMAL", "score": 0.05},
]

def test_dt_chain05_chain_linkage():
    """DT-CHAIN-05: 5-record chain built by production matches reference link-by-link."""
    prev_prod = GENESIS_PREVIOUS_HASH
    prev_ref = GENESIS

    for i, payload in enumerate(_CHAIN_PAYLOADS):
        _, prod_ph, prod_rh = build_audit_record_hashes(payload, previous_hash=prev_prod)
        ref_ph = payload_hash(payload)
        ref_rh = record_hash(prev_ref, ref_ph)

        assert prod_ph == ref_ph, (
            f"[DT-CHAIN-05] Payload hash mismatch at record {i+1}: "
            f"prod={prod_ph}, ref={ref_ph}"
        )
        assert prod_rh == ref_rh, (
            f"[DT-CHAIN-05] Record hash mismatch at record {i+1}: "
            f"prod={prod_rh}, ref={ref_rh}"
        )

        prev_prod = prod_rh
        prev_ref = ref_rh


# ── DT-CHAIN-06: Diverse payload types ───────────────────────────────────────

def test_dt_chain06_diverse_payloads():
    """DT-CHAIN-06: Payloads with floats, unicode, nested dicts, and datetime."""
    payloads = [
        {"floats": [0.1, 0.2, 0.3], "name": "café"},
        {"nested": {"a": {"b": {"c": 42}}}},
        {"ts": datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)},
        {"labels": ["benign", "attack", "benign"], "conf": [0.9, 0.05, 0.85]},
        {"big_int": 2 ** 53, "neg": -(2 ** 31)},
    ]
    for payload in payloads:
        prod_ph = calculate_payload_hash(payload)
        ref_ph = payload_hash(payload)
        assert prod_ph == ref_ph, (
            f"[DT-CHAIN-06] Payload hash mismatch for {payload!r}\n"
            f"  prod={prod_ph}\n  ref={ref_ph}"
        )


# ── DT-CHAIN-07: Payload-hash sensitivity ────────────────────────────────────

def test_dt_chain07_payload_sensitivity():
    """DT-CHAIN-07: Changing any single field in the payload changes the hash."""
    base = {"event": "login", "user": "alice", "score": 0.5}
    mutations = [
        {**base, "event": "LOGOUT"},       # change a value
        {**base, "user": "bob"},
        {**base, "score": 0.50000001},     # tiny float change
        {**base, "extra_key": "injected"}, # add a field
    ]
    base_hash = calculate_payload_hash(base)
    for mut in mutations:
        mut_hash = calculate_payload_hash(mut)
        assert base_hash != mut_hash, (
            f"[DT-CHAIN-07] Hash collision: same hash for different payloads\n"
            f"  base: {base}\n  mut: {mut}"
        )


# ── DT-CHAIN-08: Record hash covers both prev_hash and payload_hash ───────────

def test_dt_chain08_record_hash_covers_both():
    """DT-CHAIN-08: Changing either prev_hash or payload_hash changes record_hash."""
    ph = "a" * 64
    prev1 = "0" * 64
    prev2 = "1" * 64  # different previous hash

    rh1 = calculate_record_hash(prev1, ph)
    rh2 = calculate_record_hash(prev2, ph)
    assert rh1 != rh2, "[DT-CHAIN-08] Record hash insensitive to prev_hash change"

    prev = "0" * 64
    ph1 = "a" * 64
    ph2 = "b" * 64  # different payload hash

    rh_a = calculate_record_hash(prev, ph1)
    rh_b = calculate_record_hash(prev, ph2)
    assert rh_a != rh_b, "[DT-CHAIN-08] Record hash insensitive to payload_hash change"


# ── Extra: build_chain round-trip and verify ──────────────────────────────────

def test_dt_chain09_build_chain_round_trip():
    """DT-CHAIN-09: build_chain produces a chain that verifies correctly."""
    payloads = [
        {"event": "login", "user": "alice"},
        {"event": "logout", "user": "alice"},
        {"event": "login", "user": "bob"},
    ]
    chain = build_chain(payloads)
    assert len(chain) == 3, f"Expected 3 records, got {len(chain)}"

    for i, rec in enumerate(chain, start=1):
        assert rec["sequence_number"] == i
        assert rec["previous_hash"] == ("0" * 64) if i == 1 else chain[i - 2]["record_hash"]
        assert len(rec["payload_hash"]) == 64
        assert len(rec["record_hash"]) == 64
        assert rec["payload_json"] == ref_canonical_json_for_chain(payloads[i - 1])

    ok, errors = verify_chain(chain)
    assert ok, f"Chain did not verify: {errors}"


def test_dt_chain10_verify_record_detects_tampered_previous_hash():
    """DT-CHAIN-10: verify_record detects a tampered previous_hash pointer.

    The chain-level verifier checks the previous_hash pointer; the record-level
    verify_record recomputes record_hash, which fails when the stored
    record_hash does not cover the new previous_hash.
    """
    payloads = [{"event": "login", "user": "alice"}]
    chain = build_chain(payloads)
    record = dict(chain[0])

    # Tamper the previous-hash pointer.
    record["previous_hash"] = "b" * 64

    ok, errors = verify_record(record)
    assert ok is False, f"verify_record must detect tampered previous_hash: {errors}"
    assert any("record_hash mismatch" in e for e in errors), f"Errors: {errors}"


def test_dt_chain11_verify_chain_with_gap():
    """DT-CHAIN-11: verify_chain detects a sequence gap."""
    payloads = [{"seq": i} for i in range(1, 5)]
    chain = build_chain(payloads)
    gapped = [r for r in chain if r["sequence_number"] != 3]
    ok, errors = verify_chain(gapped)
    assert not ok, f"Chain with gap should not verify: {errors}"
    assert any("sequence gap" in e for e in errors), f"Errors: {errors}"


def test_dt_chain12_verify_chain_detects_tampered_record_hash():
    """DT-CHAIN-12: verify_chain detects a forged record_hash."""
    payloads = [{"event": "login", "user": "alice"}, {"event": "logout"}]
    chain = build_chain(payloads)
    tampered = list(chain)
    tampered[0]["record_hash"] = "f" * 64
    ok, errors = verify_chain(tampered)
    assert not ok, f"Chain with forged record_hash should not verify: {errors}"
    assert any("record_hash mismatch" in e for e in errors), f"Errors: {errors}"


def test_dt_chain13_verify_chain_detects_tampered_previous_hash():
    """DT-CHAIN-13: verify_chain detects a tampered previous_hash pointer."""
    payloads = [{"event": "login"}, {"event": "logout"}]
    chain = build_chain(payloads)
    tampered = list(chain)
    tampered[1]["previous_hash"] = "a" * 64
    ok, errors = verify_chain(tampered)
    assert not ok, f"Chain with tampered previous_hash should not verify: {errors}"
    assert any("previous_hash mismatch" in e for e in errors), f"Errors: {errors}"


def test_dt_chain14_verify_chain_detects_tampered_payload():
    """DT-CHAIN-14: verify_chain detects a tampered payload.

    When the stored record_hash is NOT recomputed after a payload change, the
    recomputed record hash no longer matches the stored one, so verification
    fails. (The chain has no reference copy of the original payload.)
    """
    payloads = [{"event": "login", "user": "alice"}]
    chain = build_chain(payloads)
    tampered = list(chain)
    original = tampered[0]
    payload_obj = json.loads(original["payload_json"])
    payload_obj["user"] = "mallory"
    tampered[0] = _MockRecord(
        sequence_number=original["sequence_number"],
        payload_json=json.dumps(payload_obj, sort_keys=True, separators=(",", ":")),
        previous_hash=original["previous_hash"],
        record_hash=original["record_hash"],  # NOT updated to reflect the new payload
        id=original.get("id", ""),
    )
    ok, errors = verify_chain([{
        "sequence_number": r["sequence_number"],
        "payload_json": r["payload_json"],
        "previous_hash": r["previous_hash"],
        "record_hash": r["record_hash"],
    } for r in tampered])
    assert not ok, f"Chain with tampered payload should not verify: {errors}"
    assert any("record_hash mismatch" in e for e in errors), f"Errors: {errors}"


def test_dt_chain15_verify_chain_detects_tampered_previous_hash():
    """DT-CHAIN-15: verify_chain detects a tampered previous_hash pointer."""
    payloads = [{"event": "login"}, {"event": "logout"}]
    chain = build_chain(payloads)
    tampered = list(chain)
    tampered[1]["previous_hash"] = "a" * 64
    ok, errors = verify_chain(tampered)
    assert not ok, f"Chain with tampered previous_hash should not verify: {errors}"
    assert any("previous_hash mismatch" in e for e in errors), f"Errors: {errors}"


def _MockRecord(sequence_number, payload_json, previous_hash, record_hash, id=""):
    """Minimal object exposing the attributes verify_ledger/verify_chain need.

    Returns a plain dict so it works with both an ORM-backed verifier and the
    reference chain verifier.
    """
    return {
        "sequence_number": sequence_number,
        "payload_json": payload_json,
        "previous_hash": previous_hash,
        "record_hash": record_hash,
        "id": id,
    }
