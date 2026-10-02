"""Differential tests — Hash-chain construction.

Compares the production hash-chain module
(backend.app.cryptography.hash_chain) against the reference implementation
(backend.app.cryptography.reference).

The reference builds payload_hash and record_hash entirely independently,
using only hashlib and Python built-ins, so any production regression that
silently changes hash linkage will be caught.

Component: hash_chain
Tests:
  DT-CHAIN-01  calculate_payload_hash matches reference for simple payloads
  DT-CHAIN-02  calculate_record_hash(prev, payload_hash) matches reference
  DT-CHAIN-03  build_audit_record_hashes triple: canonical, payload_hash, record_hash
  DT-CHAIN-04  Genesis record (previous_hash = '0'*64) matches reference
  DT-CHAIN-05  Chain link: record N's record_hash used as previous_hash for record N+1
  DT-CHAIN-06  Diverse payload types (floats, unicode, nested dicts, datetime)
  DT-CHAIN-07  Payload-hash sensitivity (changing one field changes hash)
  DT-CHAIN-08  Record-hash covers both prev_hash and payload_hash (both required)
"""
from __future__ import annotations

import hashlib
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
from backend.app.cryptography.reference import (
    GENESIS,
    ref_canonical_json,
    ref_payload_hash,
    ref_record_hash,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ref_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
    ref = ref_payload_hash(payload)
    assert prod == ref, (
        f"[DT-CHAIN-01] Payload hash mismatch for {payload!r}\n"
        f"  production: {prod}\n"
        f"  reference : {ref}"
    )
    # Must be a 64-char hex string
    assert len(prod) == 64 and all(c in "0123456789abcdef" for c in prod), (
        f"[DT-CHAIN-01] Invalid hash format: {prod!r}"
    )


# ── DT-CHAIN-02: Record hash matches reference ────────────────────────────────

_RECORD_HASH_CASES = [
    ("0" * 64, "a" * 64),
    ("dead" + "beef" * 15, "cafe" + "babe" * 15),   # padded to 64 hex chars each
    (GENESIS_PREVIOUS_HASH, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
]

# Ensure all test tuples have 64-char hex strings
_RECORD_HASH_CASES_VALID = [
    ("0" * 64, "a" * 64),
    ("d" * 64, "e" * 64),
    (GENESIS_PREVIOUS_HASH, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
]

@pytest.mark.parametrize("prev_hash,payload_hash", _RECORD_HASH_CASES_VALID)
def test_dt_chain02_record_hash(prev_hash, payload_hash):
    """DT-CHAIN-02: calculate_record_hash matches reference record hash."""
    prod = calculate_record_hash(prev_hash, payload_hash)
    ref = ref_record_hash(prev_hash, payload_hash)
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

    # Reference computations (independent path)
    ref_canon = ref_canonical_json(payload)
    ref_ph = ref_payload_hash(payload)
    ref_rh = ref_record_hash(prev_hash, ref_ph)

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
        ref_ph = ref_payload_hash(payload)
        ref_rh = ref_record_hash(prev_ref, ref_ph)

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
        ref_ph = ref_payload_hash(payload)
        assert prod_ph == ref_ph, (
            f"[DT-CHAIN-06] Payload hash mismatch for {payload!r}\n"
            f"  prod={prod_ph}\n  ref={ref_ph}"
        )


# ── DT-CHAIN-07: Payload hash sensitivity ────────────────────────────────────

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
    assert rh1 != rh2, (
        "[DT-CHAIN-08] Record hash insensitive to prev_hash change"
    )

    prev = "0" * 64
    ph1 = "a" * 64
    ph2 = "b" * 64  # different payload hash

    rh_a = calculate_record_hash(prev, ph1)
    rh_b = calculate_record_hash(prev, ph2)
    assert rh_a != rh_b, (
        "[DT-CHAIN-08] Record hash insensitive to payload_hash change"
    )
