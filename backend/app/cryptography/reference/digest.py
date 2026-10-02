"""SHA-256 digest helpers for the SentinelCrypt evidence protocol.

Reference implementation of ``backend.app.cryptography.hashing``.
Deliberately naive — plain ``hashlib`` with no glue code — so the differential
tests in ``test_hashing_differential.py`` compare an independent re-implementation
against the production module.
"""

from __future__ import annotations

import hashlib
from typing import Union

__all__ = ["sha256_hex", "sha256_bytes"]


def sha256_hex(data: Union[str, bytes]) -> str:
    """Compute 64-character lowercase hexadecimal SHA-256 digest.

    ``str`` inputs are UTF-8 encoded first.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute 64-character lowercase hexadecimal SHA-256 digest over raw bytes."""
    return hashlib.sha256(data).hexdigest()
