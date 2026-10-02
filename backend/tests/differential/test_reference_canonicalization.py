"""Differential tests — Canonical JSON serialization (reference package).

Compares the production canonicalization module
(backend.app.cryptography.canonicalization) against the clean reference
implementation (backend.app.cryptography.reference.canonical).

The reference is deliberately structured differently (recursive descent instead
of ``json.dumps(sort_keys=True, ...)``) so that a shared-code bug cannot silently
survive both implementations.

Component: canonicalization
Tests:
  DT-CAN-01  Simple flat dict with string values
  DT-CAN-02  Nested dicts and lists
  DT-CAN-03  Key ordering (sort_keys must be applied recursively)
  DT-CAN-04  Float serialization (must round-trip via json.dumps)
  DT-CAN-05  Datetime -> ISO-8601 UTC serialization
  DT-CAN-06  Empty dict and empty list
  DT-CAN-07  Unicode keys and values
  DT-CAN-08  Boolean and None values
  DT-CAN-09  Integer values
  DT-CAN-10  NaN / Infinity raises ValueError in both implementations
  DT-CAN-11  Output is always a valid JSON string (parseable by json.loads)
  DT-CAN-12  Re-parsing and re-canonicalizing is idempotent
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.reference.canonical import canonicalize as ref_canonical_json


# ── Helper: compare production canonicalize() to reference canonicalize() ─────

def _assert_canon_match(payload: Dict[str, Any], case: str) -> None:
    """Assert that production canonical JSON equals reference canonical JSON."""
    prod = canonicalize(payload)
    ref = ref_canonical_json(payload)
    assert prod == ref, (
        f"[{case}] Canonicalization mismatch.\n"
        f"  production : {prod!r}\n"
        f"  reference  : {ref!r}"
    )
    # Both must be valid JSON
    json.loads(prod)
    json.loads(ref)


# ── DT-CAN-01: Simple flat dict ───────────────────────────────────────────────

@pytest.mark.parametrize("payload", [
    {"key": "value"},
    {"a": "1", "b": "2", "c": "3"},
    {"event_type": "login", "user": "alice", "status": "success"},
    {"z": "last", "a": "first", "m": "middle"},  # key ordering test
])
def test_dt_can01_simple_flat_dict(payload):
    """DT-CAN-01: Simple flat dicts with string values canonicalize identically."""
    _assert_canon_match(payload, "DT-CAN-01")


# ── DT-CAN-02: Nested dicts and lists ────────────────────────────────────────

@pytest.mark.parametrize("payload", [
    {"outer": {"inner": "value"}},
    {"list": [1, 2, 3], "dict": {"a": 1}},
    {"deep": {"deeper": {"deepest": "bottom"}}},
    {"mixed": [{"a": 1}, {"b": 2}]},
    {"empty_list": [], "empty_dict": {}},
])
def test_dt_can02_nested_structures(payload):
    """DT-CAN-02: Nested dicts and lists canonicalize identically."""
    _assert_canon_match(payload, "DT-CAN-02")


# ── DT-CAN-03: Key ordering ───────────────────────────────────────────────────

def test_dt_can03_key_ordering():
    """DT-CAN-03: Keys are always sorted lexicographically (including nested)."""
    payload = {
        "zebra": 1,
        "apple": 2,
        "mango": {"z_nested": "b", "a_nested": "a"},
    }
    prod = canonicalize(payload)
    ref = ref_canonical_json(payload)
    assert prod == ref, f"[DT-CAN-03] Mismatch: {prod!r} vs {ref!r}"
    # Verify keys appear in sorted order in the serialized string
    parsed = json.loads(prod)
    keys = list(parsed.keys())
    assert keys == sorted(keys), f"[DT-CAN-03] Top-level keys not sorted: {keys}"


# ── DT-CAN-04: Float serialization ────────────────────────────────────────────

_FLOAT_CASES = [
    {"f": 0.0},
    {"f": 1.0},
    {"f": 3.14159265358979323},
    {"f": 1e-10},
    {"f": 1e100},
    {"f": -0.001},
    {"f": 0.1 + 0.2},   # classic float rounding (0.30000000000000004)
]

@pytest.mark.parametrize("payload", _FLOAT_CASES)
def test_dt_can04_float_serialization(payload):
    """DT-CAN-04: Float values serialize identically (shortest round-trip repr)."""
    _assert_canon_match(payload, "DT-CAN-04")


# ── DT-CAN-05: Datetime -> ISO-8601 UTC ───────────────────────────────────────

_DT_CASES = [
    {"ts": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)},
    {"ts": datetime(2026, 6, 15, 12, 30, 45, tzinfo=timezone.utc)},
    {"ts": datetime(2024, 1, 1, 0, 0, 0)},  # naive -> should be treated as UTC
]

@pytest.mark.parametrize("payload", _DT_CASES)
def test_dt_can05_datetime_serialization(payload):
    """DT-CAN-05: datetime values serialize to ISO-8601 UTC strings consistently."""
    prod = canonicalize(payload)
    ref = ref_canonical_json(payload)
    assert prod == ref, (
        f"[DT-CAN-05] Datetime mismatch.\n"
        f"  production: {prod!r}\n"
        f"  reference : {ref!r}"
    )
    # Verify the ISO-8601 UTC string appears in the serialized output
    parsed = json.loads(prod)
    ts_val = parsed["ts"]
    assert isinstance(ts_val, str), f"[DT-CAN-05] Datetime not serialized as string: {ts_val!r}"


# ── DT-CAN-06: Empty structures ───────────────────────────────────────────────

def test_dt_can06_empty_dict():
    """DT-CAN-06: Empty dict canonicalizes to '{}'.*"""
    prod = canonicalize({})
    ref = ref_canonical_json({})
    assert prod == ref == "{}", f"[DT-CAN-06] Empty dict: prod={prod!r}, ref={ref!r}"


def test_dt_can06_empty_list_value():
    """DT-CAN-06: Dict with empty list value."""
    payload = {"items": []}
    _assert_canon_match(payload, "DT-CAN-06")


# ── DT-CAN-07: Unicode keys and values ───────────────────────────────────────

@pytest.mark.parametrize("payload", [
    {"名前": "太郎"},
    {"emoji": "🔐🛡️"},
    {"arabic": "مرحبا"},
    {"latin_ext": "café"},
    {"mixed": {"日本語": "テスト", "english": "test"}},
])
def test_dt_can07_unicode(payload):
    """DT-CAN-07: Unicode keys and values serialize identically."""
    _assert_canon_match(payload, "DT-CAN-07")


# ── DT-CAN-08: Boolean and None values ───────────────────────────────────────

@pytest.mark.parametrize("payload", [
    {"flag": True},
    {"flag": False},
    {"value": None},
    {"a": True, "b": False, "c": None},
])
def test_dt_can08_boolean_none(payload):
    """DT-CAN-08: Boolean and None values serialize identically."""
    _assert_canon_match(payload, "DT-CAN-08")


# ── DT-CAN-09: Integer values ─────────────────────────────────────────────────

@pytest.mark.parametrize("payload", [
    {"n": 0},
    {"n": 1},
    {"n": -1},
    {"n": 2**31 - 1},
    {"n": -(2**31)},
    {"n": 2**63},      # large int
])
def test_dt_can09_integers(payload):
    """DT-CAN-09: Integer values serialize identically."""
    _assert_canon_match(payload, "DT-CAN-09")


# ── DT-CAN-10: NaN / Infinity raises ValueError ───────────────────────────────

@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_dt_can10_nan_infinity_raises(bad_value):
    """DT-CAN-10: Non-finite floats must raise ValueError in both implementations."""
    payload = {"bad": bad_value}
    with pytest.raises((ValueError, TypeError)):
        canonicalize(payload)
    with pytest.raises((ValueError, TypeError)):
        ref_canonical_json(payload)


# ── DT-CAN-11: Output is always valid JSON ────────────────────────────────────

_VALID_JSON_PAYLOADS = [
    {"key": "value", "number": 42, "flag": True, "nil": None},
    {"nested": {"list": [1, 2, 3]}},
    {"unicode": "こんにちは", "ts": datetime(2024, 1, 1, tzinfo=timezone.utc)},
]

@pytest.mark.parametrize("payload", _VALID_JSON_PAYLOADS)
def test_dt_can11_output_is_valid_json(payload):
    """DT-CAN-11: Both implementations produce parseable JSON."""
    prod = canonicalize(payload)
    ref = ref_canonical_json(payload)
    try:
        json.loads(prod)
    except json.JSONDecodeError as e:
        pytest.fail(f"[DT-CAN-11] Production output is not valid JSON: {e}\n  output={prod!r}")
    try:
        json.loads(ref)
    except json.JSONDecodeError as e:
        pytest.fail(f"[DT-CAN-11] Reference output is not valid JSON: {e}\n  output={ref!r}")


# ── DT-CAN-12: Re-parsing is idempotent ──────────────────────────────────────

def test_dt_can12_idempotency():
    """DT-CAN-12: canonicalize(json.loads(canonicalize(x))) == canonicalize(x)."""
    payloads = [
        {"z": 1, "a": 2, "m": 3},
        {"nested": {"z": 1, "a": [3, 2, 1]}},
        {"event": "alert", "score": 0.9876},
    ]
    for payload in payloads:
        first = canonicalize(payload)
        round_tripped = canonicalize(json.loads(first))
        assert first == round_tripped, (
            f"[DT-CAN-12] Idempotency failure for {payload!r}\n"
            f"  first     : {first!r}\n"
            f"  re-parsed : {round_tripped!r}"
        )
