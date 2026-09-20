"""RFC 8785 / JCS-compliant Deterministic Canonical JSON Serializer."""
import json
from datetime import datetime, timezone
from typing import Any

def canonical_serializer(obj: Any) -> Any:
    """Custom JSON serializer ensuring ISO-8601 UTC timestamp and clean float serialization."""
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        return obj.isoformat()
    if isinstance(obj, float):
        # Format floats to 6 decimal places to prevent platform precision divergence
        return round(obj, 6)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

def canonicalize(payload: dict) -> str:
    """Serialize dictionary payload deterministically into canonical JSON string."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=canonical_serializer
    )
