"""Property tests for deterministic serialization and audit evidence.

Properties compare production behavior with an independent reference or assert
an invariant of records constructed from the production protocol.
"""
from __future__ import annotations

import hashlib
import json

from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    build_audit_record_hashes,
    calculate_payload_hash,
    calculate_record_hash,
)
from backend.app.cryptography.reference import (
    ref_canonical_json,
    ref_payload_hash,
    ref_record_hash,
)
from backend.app.cryptography.verifier import verify_ledger


JSON_SCALAR = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=30)
)
JSON_VALUE = st.recursive(
    JSON_SCALAR,
    lambda children: st.lists(children, max_size=6)
    | st.dictionaries(st.text(max_size=12), children, max_size=6),
    max_leaves=16,
)
JSON_OBJECT = st.dictionaries(st.text(max_size=12), JSON_VALUE, max_size=8)
PROPERTY_SETTINGS = settings(max_examples=100, derandomize=True, deadline=None)


class Row:
    def __init__(self, values):
        for key, value in values.items():
            setattr(self, key, value)


@given(JSON_VALUE)
@PROPERTY_SETTINGS
def test_canonical_json_matches_independent_reference(value):
    encoded = canonicalize(value)

    assert encoded == ref_canonical_json(value)
    assert json.loads(encoded) == value


@given(JSON_OBJECT)
@PROPERTY_SETTINGS
def test_object_key_insertion_order_does_not_change_digest(payload):
    reversed_items = dict(reversed(list(payload.items())))

    assert canonicalize(payload) == canonicalize(reversed_items)
    assert calculate_payload_hash(payload) == calculate_payload_hash(reversed_items)


@given(JSON_OBJECT)
@PROPERTY_SETTINGS
def test_payload_hash_matches_independent_sha256_reference(payload):
    expected = hashlib.sha256(ref_canonical_json(payload).encode("utf-8")).hexdigest()

    assert calculate_payload_hash(payload) == ref_payload_hash(payload) == expected


@given(
    previous_hash=st.text(
        alphabet="0123456789abcdef", min_size=64, max_size=64
    ),
    payload_hash=st.text(
        alphabet="0123456789abcdef", min_size=64, max_size=64
    ),
)
@PROPERTY_SETTINGS
def test_record_hash_matches_protocol_formula(previous_hash, payload_hash):
    expected = hashlib.sha256(
        (previous_hash + payload_hash).encode("ascii")
    ).hexdigest()

    assert calculate_record_hash(previous_hash, payload_hash) == expected
    assert calculate_record_hash(previous_hash, payload_hash) == ref_record_hash(
        previous_hash, payload_hash
    )


@given(st.lists(JSON_VALUE, min_size=1, max_size=12))
@PROPERTY_SETTINGS
def test_any_honestly_constructed_chain_verifies(payloads):
    records = []
    previous_hash = GENESIS_PREVIOUS_HASH

    for sequence, value in enumerate(payloads, start=1):
        payload = {"sequence": sequence, "value": value}
        canonical_payload, _, record_hash = build_audit_record_hashes(
            payload, previous_hash
        )
        records.append({
            "sequence_number": sequence,
            "payload_json": canonical_payload,
            "previous_hash": previous_hash,
            "record_hash": record_hash,
        })
        previous_hash = record_hash

    assert verify_ledger([Row(record) for record in records]).verified


@given(JSON_VALUE)
@PROPERTY_SETTINGS
def test_changing_any_committed_payload_breaks_chain_verification(value):
    payload = {"sequence": 1, "value": value}
    canonical_payload, _, record_hash = build_audit_record_hashes(payload)
    changed_payload = dict(payload, tamper_marker="changed")
    record = {
        "sequence_number": 1,
        "payload_json": canonical_payload,
        "previous_hash": GENESIS_PREVIOUS_HASH,
        "record_hash": record_hash,
    }
    record["payload_json"] = canonicalize(changed_payload)

    assert not verify_ledger([Row(record)]).verified


def test_regression_reference_serialization_handles_nested_unicode_and_zero():
    payload = {"nested": {"café": [0, -0.0, "雪"]}, "a": True}

    assert canonicalize(payload) == '{"a":true,"nested":{"café":[0,-0.0,"雪"]}}'
    assert canonicalize(payload) == ref_canonical_json(payload)


def test_regression_non_finite_numbers_are_rejected_from_canonical_form():
    import math
    import pytest

    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError):
            canonicalize({"value": value})
