"""Deterministic JSON serialization for the SentinelCrypt evidence protocol.

Reference implementation of ``backend.app.cryptography.canonicalization``.
Deliberately structured differently (recursive descent instead of
``json.dumps(sort_keys=True, ...)``) so the two implementations do not share
code; this is a test oracle, not a production path.

Protocol semantics
------------------
1. Objects are serialized with ``json.dumps``.
2. Keys are sorted lexicographically (the ``sort_keys`` rule).
3. Whitespace is removed (``separators=(",", ":")``).
4. Non-ASCII characters are preserved as-is (``ensure_ascii=False``).
5. Floats use the Python JSON encoder's representation. NaN and Infinity
   raise ``ValueError``.
6. Datetime values use ``datetime.isoformat()``; naive datetimes are treated
   as UTC, while timezone-aware offsets are preserved.

This is SentinelCrypt's Python serialization convention, not an
implementation of RFC 8785/JCS. Payload object keys must be strings.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

__all__ = ["canonicalize"]


def canonicalize(payload: Any) -> str:
    """Serialize ``payload`` into canonical JSON for the evidence protocol.

    Deterministic output guarantees that identical logical payloads always
    produce identical strings, which is what makes SHA-256 of the
    canonical representation usable as an integrity digest.
    """
    return _encode_value(payload)


def _encode_value(value: Any) -> str:
    """Recursively encode values using the documented local convention."""
    if value is None or value is True or value is False:
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(
                f"Non-finite float {value!r} cannot be canonically serialized "
                "(NaN/Infinity are not JSON)."
            )
        return json.dumps(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return json.dumps(value.isoformat(), ensure_ascii=False)
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("Canonical JSON object keys must be strings.")
        items = sorted(value.items())
        body = ",".join(
            json.dumps(k, ensure_ascii=False) + ":" + _encode_value(v) for k, v in items
        )
        return "{" + body + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_encode_value(v) for v in value) + "]"
    raise TypeError(
        f"Unsupported type for canonicalization: {type(value).__name__}"
    )
