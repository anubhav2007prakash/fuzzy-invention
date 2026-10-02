"""RFC 8785 / JCS-compliant Deterministic Canonical JSON Serializer."""
import json
import math
from datetime import datetime, timezone
from typing import Any

def canonical_serializer(obj: Any) -> Any:
    """Custom JSON serializer ensuring ISO-8601 UTC timestamp and clean float serialization."""
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        return obj.isoformat()
    if isinstance(obj, float):
        # NaN/Infinity are NOT valid JSON (RFC 8785): silently emitting the
        # non-standard `NaN` token would make digests unverifiable outside
        # Python and divergence-prone.  Reject them loudly instead.
        if not math.isfinite(obj):
            raise ValueError(
                f"Non-finite float {obj!r} cannot be canonically serialized "
                "(NaN/Infinity are not JSON)."
            )
        return obj
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

def canonicalize(payload: dict) -> str:
    """Serialize dictionary payload deterministically into canonical JSON string."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=canonical_serializer
    )
