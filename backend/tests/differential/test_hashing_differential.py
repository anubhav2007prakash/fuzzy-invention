"""Differential tests  SHA-256 hashing.

Compares the production hashing module (backend.app.cryptography.hashing)
against an independent reference re-implementation that uses only Python's
hashlib directly (no helper functions from the production path).

Component: hashing
Tests:
  DT-HASH-01  sha256_hash with ASCII string inputs
  DT-HASH-02  sha256_hash with Unicode / multibyte strings
  DT-HASH-03  sha256_hash with empty string
  DT-HASH-04  sha256_hash with raw bytes input
  DT-HASH-05  Output is always 64-char lowercase hex
  DT-HASH-06  Determinism: same input always produces same hash
  DT-HASH-07  Sensitivity: single-bit change produces different hash
  DT-HASH-08  Known-answer vector (NIST SHA-256 test vector)
"""
from __future__ import annotations

import hashlib
import pytest

from backend.app.cryptography.hashing import sha256_hash
from backend.app.cryptography.reference.digest import sha256_bytes, sha256_hex


#  Reference implementation 

def _ref_sha256(data: str | bytes) -> str:
    """Deliberately naive reference: no helpers, just raw hashlib."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


#  DT-HASH-01: ASCII string inputs 

_ASCII_CASES = [
    "hello",
    "world",
    "SentinelCrypt AI",
    "abc123",
    "The quick brown fox jumps over the lazy dog",
    "a" * 1000,
    "0" * 64,
]

@pytest.mark.parametrize("text", _ASCII_CASES, ids=[repr(t[:20]) for t in _ASCII_CASES])
def test_dt_hash01_ascii_strings(text):
    """DT-HASH-01: SHA-256 of ASCII strings matches reference."""
    prod = sha256_hash(text)
    ref = _ref_sha256(text)
    assert prod == ref, (
        f"[DT-HASH-01] Mismatch for input {text!r}\n"        f"  production: {prod}\n"        f"  reference : {ref}"
    )
    assert prod == sha256_hex(text), (
        f"[DT-HASH-01] Production/reference mismatch for {text!r}: "
        f"production={prod}, reference={sha256_hex(text)}"
    )


#  DT-HASH-02: Unicode / multibyte strings 

_UNICODE_CASES = [
    "",           # Japanese
    "",               # Arabic
    " ",           # Russian
    "",              # Emoji
    "caf nave rsum",   # Latin with diacritics
    "\u0000null\u0000byte", # Null bytes
]

@pytest.mark.parametrize("text", _UNICODE_CASES, ids=[repr(t[:12]) for t in _UNICODE_CASES])
def test_dt_hash02_unicode_strings(text):
    """DT-HASH-02: SHA-256 of Unicode strings matches reference (UTF-8 encoding)."""
    prod = sha256_hash(text)
    ref = _ref_sha256(text)
    assert prod == ref, (
        f"[DT-HASH-02] Unicode mismatch for {text!r}\n"        f"  production: {prod}\n"        f"  reference : {ref}"
    )
    assert prod == sha256_hex(text), (
        f"[DT-HASH-02] Production/reference mismatch for {text!r}: "
        f"production={prod}, reference={sha256_hex(text)}"
    )


#  DT-HASH-03: Empty string 

def test_dt_hash03_empty_string():
    """DT-HASH-03: SHA-256("") matches known NIST value and reference."""
    KNOWN_SHA256_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    prod = sha256_hash("")
    ref = _ref_sha256("")
    assert prod == ref, f"[DT-HASH-03] Empty string: prod={prod}, ref={ref}"
    assert prod == KNOWN_SHA256_EMPTY, (
        f"[DT-HASH-03] Empty string known-answer mismatch: {prod}"
    )


#  DT-HASH-04: Raw bytes input 

_BYTES_CASES = [
    b"",
    b"\x00",
    bytes(range(256)),
    b"\xff\xfe\xfd",
    b"SentinelCrypt",
]

@pytest.mark.parametrize("data", _BYTES_CASES, ids=[repr(d[:8]) for d in _BYTES_CASES])
def test_dt_hash04_bytes_input(data):
    """DT-HASH-04: SHA-256 of bytes input matches reference."""
    prod = sha256_hash(data)
    ref = _ref_sha256(data)
    assert prod == ref, (
        f"[DT-HASH-04] Bytes mismatch for {data!r}\n"        f"  production: {prod}\n"        f"  reference : {ref}"
    )
    assert prod == sha256_bytes(data)


#  DT-HASH-05: Output format 

@pytest.mark.parametrize("text", ["test", "", "x" * 10000])
def test_dt_hash05_output_format(text):
    """DT-HASH-05: Output is always 64-character lowercase hex string."""
    result = sha256_hash(text)
    assert isinstance(result, str), f"[DT-HASH-05] Expected str, got {type(result)}"
    assert len(result) == 64, f"[DT-HASH-05] Expected length 64, got {len(result)}"
    assert result == result.lower(), f"[DT-HASH-05] Output not lowercase: {result}"
    assert all(c in "0123456789abcdef" for c in result), (
        f"[DT-HASH-05] Non-hex characters in output: {result}"
    )


#  DT-HASH-06: Determinism 

def test_dt_hash06_determinism():
    """DT-HASH-06: Repeated calls with same input produce identical output."""
    inputs = ["sentinel", "aBcDeF123", "   spaces   "]
    for text in inputs:
        hashes = [sha256_hash(text) for _ in range(10)]
        assert len(set(hashes)) == 1, (
            f"[DT-HASH-06] Non-deterministic output for {text!r}: {set(hashes)}"
        )


#  DT-HASH-07: Single-bit sensitivity (avalanche) 

def test_dt_hash07_avalanche():
    """DT-HASH-07: Flipping a single byte produces a different hash."""
    original = b"SentinelCrypt audit hash"
    modified = bytes([original[0] ^ 0x01]) + original[1:]
    h_orig = sha256_hash(original)
    h_mod = sha256_hash(modified)
    assert h_orig != h_mod, (
        f"[DT-HASH-07] Avalanche test failed: identical hashes for different inputs"
    )


#  DT-HASH-08: NIST known-answer test vectors 

_NIST_VECTORS = [
    ("abc", "ba7816bf8f01cfea414140de5dae2ec73b00361bbef0469f490f67bc37d0f61a"),
    ("", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    ("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
     "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"),
]
     "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"),
]

def test_dt_hash08_known_answer_vectors(text, expected):
    """DT-HASH-08: NIST SHA-256 known-answer test vectors."""
    prod = sha256_hash(text)
    ref = _ref_sha256(text)
    assert prod == expected, (
        f"[DT-HASH-08] Known-answer failure for {text!r}\n"
        f"  expected  : {expected}\n"
        f"  production: {prod}"
    )
    assert ref == expected, (
        f"[DT-HASH-08] Reference known-answer failure for {text!r}\n"
        f"  expected : {expected}\n"
        f"  reference: {ref}"
    )
    assert prod == reference_module, (
        f"[DT-HASH-08] Production/reference mismatch for {text!r}: "
        f"production={prod}, reference={reference_module}"
    )
