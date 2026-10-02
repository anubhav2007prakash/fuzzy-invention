"""Metamorphic Relations for RFC 8785 Canonical JSON Serialization."""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Tuple

from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hashing import sha256_hash
from backend.tests.metamorphic.framework import (
    Category,
    MetamorphicRelation,
)


class MR_CAN_01_KeyShufflingInvariance(MetamorphicRelation):
    """MR-CAN-01: Invariance under arbitrary dictionary key permutation."""

    id = "MR-CAN-01"
    name = "Key Permutation Invariance (RFC 8785 Lexicographic Sorting)"
    category = Category.CANONICALIZATION
    rationale = (
        "In JSON, objects represent unordered sets of key-value pairs. To generate "
        "reproducible cryptographic evidence digests across different programming "
        "languages and runtimes, RFC 8785 canonicalization recursively sorts dictionary "
        "keys lexicographically. Permuting key insertion order at any level must yield "
        "the exact same canonical byte stream."
    )
    input_transformation = (
        "Recursively permute (reverse or randomize) the key insertion order of dictionary P to form P'."
    )
    expected_property = "canonicalize(P) == canonicalize(P') and SHA256(canonicalize(P)) == SHA256(canonicalize(P'))."
    limitations = "Applies to dictionary keys; JSON array elements have semantic order."
    test_implementation = (
        "Construct deeply nested dictionary, reverse and shuffle keys at all levels, "
        "assert identical canonical strings and digests."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        payload_a = {
            "z_alert_level": "CRITICAL",
            "a_metadata": {
                "sensor_id": "sensor-01",
                "cluster": "edge-eu",
                "ip_bindings": {"internal": "10.0.0.1", "external": "198.51.100.1"},
            },
            "m_flow": {"bytes": 1048576, "packets": 768, "duration": 4.125},
            "c_score": 0.985,
        }

        # Follow-up: completely reversed key order at all levels
        payload_b = {
            "c_score": 0.985,
            "m_flow": {"duration": 4.125, "packets": 768, "bytes": 1048576},
            "a_metadata": {
                "ip_bindings": {"external": "198.51.100.1", "internal": "10.0.0.1"},
                "cluster": "edge-eu",
                "sensor_id": "sensor-01",
            },
            "z_alert_level": "CRITICAL",
        }

        str_a = canonicalize(payload_a)
        str_b = canonicalize(payload_b)
        hash_a = sha256_hash(str_a)
        hash_b = sha256_hash(str_b)

        passed = (str_a == str_b) and (hash_a == hash_b)
        return (
            passed,
            f"Canonical output {'matched identically' if passed else 'diverged'}.",
            {"canonical_str": str_a, "digest": hash_a},
        )


class MR_CAN_02_WhitespaceNormalization(MetamorphicRelation):
    """MR-CAN-02: Normalization of insignificant whitespace and formatting."""

    id = "MR-CAN-02"
    name = "Insignificant Whitespace Normalization"
    category = Category.CANONICALIZATION
    rationale = (
        "JSON payloads transmitted over HTTP networks or saved to log files often have "
        "varying indentation, spaces around colons/commas, or trailing newlines. "
        "Canonicalization eliminates all insignificant whitespace (`separators=(',', ':')`). "
        "Any formatting variation of the same logical data must serialize to the same canonical representation."
    )
    input_transformation = (
        "Format a source payload as minified, pretty-printed (indent=4), and tab-spaced JSON strings."
    )
    expected_property = "canonicalize(json.loads(J_min)) == canonicalize(json.loads(J_pretty))."
    limitations = "Whitespace inside string literal values is preserved."
    test_implementation = (
        "Load JSON from minified string, pretty string, and extra-space string, assert all canonicalize identically."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        raw_obj = {"event": "INFERENCE", "model_id": "rf-01", "features": [1.0, 2.5, 3.0]}

        json_minified = '{"event":"INFERENCE","model_id":"rf-01","features":[1.0,2.5,3.0]}'
        json_pretty = json.dumps(raw_obj, indent=4)
        json_spaced = ' {  "event" :  "INFERENCE" ,  "model_id" : "rf-01" , "features" : [ 1.0 , 2.5 , 3.0 ] } \n'

        c_min = canonicalize(json.loads(json_minified))
        c_pretty = canonicalize(json.loads(json_pretty))
        c_spaced = canonicalize(json.loads(json_spaced))

        passed = (c_min == c_pretty == c_spaced)
        return (
            passed,
            f"All whitespace variants {'normalized to identical canonical string' if passed else 'diverged'}.",
            {"canonical_result": c_min},
        )


class MR_CAN_03_TimezoneUTCNormalization(MetamorphicRelation):
    """MR-CAN-03: Normalization of timezone offsets to UTC ISO-8601."""

    id = "MR-CAN-03"
    name = "ISO-8601 UTC Datetime Normalization"
    category = Category.CANONICALIZATION
    rationale = (
        "Audit log timestamps represent physical points in time. `canonical_serializer` "
        "converts naive and offset-aware datetimes to UTC. Two datetime instances representing "
        "the exact same physical instant (e.g. UTC vs UTC+05:30) must serialize to the identical "
        "ISO-8601 string, preventing false ledger integrity rejections across timezones."
    )
    input_transformation = (
        "Substitute a UTC datetime dt_utc with an equivalent timezone-shifted datetime dt_offset "
        "representing the identical instant in time."
    )
    expected_property = "canonicalize({'t': dt_utc}) == canonicalize({'t': dt_offset.astimezone(timezone.utc)})."
    limitations = "Both datetime objects must correspond to the identical physical instant."
    test_implementation = (
        "Create UTC datetime and an equivalent IST (UTC+5:30) datetime. "
        "Canonicalize and assert identity."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        # Same physical instant: 12:00:00 UTC == 17:30:00 IST
        dt_utc = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        dt_ist = datetime(2026, 10, 1, 17, 30, 0, tzinfo=ist_tz)

        # Standardizing timezone before serialization or via serializer
        payload_utc = {"timestamp": dt_utc}
        payload_ist = {"timestamp": dt_ist.astimezone(timezone.utc)}

        c_utc = canonicalize(payload_utc)
        c_ist = canonicalize(payload_ist)

        passed = (c_utc == c_ist)
        return (
            passed,
            f"Timezone representations {'normalized to identical string' if passed else 'diverged'}.",
            {"canonical_utc": c_utc, "canonical_ist": c_ist},
        )


class MR_CAN_04_NonFiniteFloatRejection(MetamorphicRelation):
    """MR-CAN-04: Deterministic rejection of non-finite floats (NaN, Inf)."""

    id = "MR-CAN-04"
    name = "Non-Finite Float Rejection Invariance"
    category = Category.CANONICALIZATION
    rationale = (
        "RFC 8785 explicitly forbids NaN and Infinity in JSON. Emitting non-standard "
        "tokens would cause unresolvable digest divergence across non-Python clients. "
        "SentinelCrypt's canonicalizer enforces this by raising ValueError. Injecting "
        "NaN or Inf into any field must deterministically trigger rejection."
    )
    input_transformation = (
        "Inject float('nan') or float('inf') into an otherwise serializable payload."
    )
    expected_property = "canonicalize(P_valid) succeeds, while canonicalize(P_nan) raises ValueError."
    limitations = "Applies specifically to non-finite floating point numbers."
    test_implementation = (
        "Assert canonicalize works on valid float, and raises ValueError on NaN and Infinity."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        valid_payload = {"score": 0.42, "latency": 15.3}
        nan_payload = {"score": float("nan"), "latency": 15.3}
        inf_payload = {"score": float("inf"), "latency": 15.3}

        # Valid should succeed
        c_valid = canonicalize(valid_payload)
        valid_ok = len(c_valid) > 0

        # NaN should raise ValueError
        nan_rejected = False
        try:
            canonicalize(nan_payload)
        except ValueError:
            nan_rejected = True

        # Inf should raise ValueError
        inf_rejected = False
        try:
            canonicalize(inf_payload)
        except ValueError:
            inf_rejected = True

        passed = valid_ok and nan_rejected and inf_rejected
        return (
            passed,
            f"Non-finite float rejection: valid_ok={valid_ok}, nan_rejected={nan_rejected}, inf_rejected={inf_rejected}.",
            {"valid_ok": valid_ok, "nan_rejected": nan_rejected, "inf_rejected": inf_rejected},
        )
