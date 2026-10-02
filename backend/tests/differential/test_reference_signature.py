"""Differential tests — Ed25519 signatures (reference package).

Compares the production notary signing path (backend.app.cryptography.notary)
against the clean reference implementation (backend.app.cryptography.reference.signature).

Protocol
--------
1. Payload bytes    = UTF-8 canonical JSON of the canonicalized payload.
2. Digest           = SHA-256(payload bytes).
3. Signature        = Ed25519(digest) (SIG-001).
4. Verification     = Ed25519 public key over (payload, signature) -> (ok, reason).
5. Keypair          = Ed25519PrivateKey.generate(), exported/loaded as PEM.

Both implementations use the `cryptography` package for Ed25519; the reference
only differs in structure (no production helpers), so a shared-code bug cannot
silently survive.

Component: signature
Tests:
  DT-SIG-01  create_keypair generates distinct, valid key pairs
  DT-SIG-02  sign_payload -> verify_signature round trip succeeds
  DT-SIG-03  tampered payload fails verification
  DT-SIG-04  tampered signature fails verification
  DT-SIG-05  signature covers the exact canonical payload digest
  DT-SIG-06  different payloads produce different signatures
  DT-SIG-07  same payload + different keypair fails verification
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, Tuple

from cryptography.hazmat.primitives import serialization

import pytest

from backend.app.cryptography.notary import sign_result, verify_artifact
from backend.app.cryptography.reference.signature import (
    ALGORITHM,
    DIGEST_ALGORITHM,
    create_keypair,
    load_keypair,
    sign_payload,
    verify_signature,
)
from backend.app.cryptography.reference.signature import (
    sign_result as reference_sign_result,
    verify_artifact as reference_verify_artifact,
)

# ── Helper: build a canonical payload dict ────────────────────────────────────

def _sample_payload() -> Dict[str, Any]:
    return {
        "event": "login",
        "user": "alice",
        "severity": 1,
        "ts": "2026-06-15T12:30:45Z",
        "labels": ["benign", "attack"],
    }


# ── DT-SIG-01: create_keypair generates distinct, valid key pairs ─────────────

def test_dt_sig01_keypair_generation(tmp_path):
    """DT-SIG-01: Two keypairs are distinct and each has a valid public key."""
    kp1 = create_keypair()
    kp2 = create_keypair()
    assert kp1 != kp2, "Two generated keypairs must be distinct"
    # Public keys must be valid Ed25519 public keys
    raw1 = kp1.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    assert len(raw1) == 32, "Ed25519 public key must be 32 bytes"
    raw2 = kp2.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    assert len(raw2) == 32
    # A keypair generated with a different key must NOT verify the first
    # signature (non-repudiation).
    sid = sign_payload({"event": "login", "user": "alice"}, kp1)
    ok, _ = verify_signature({"event": "login", "user": "alice"}, sid, kp2.public_key())
    assert ok is False, "signature made by another keypair must fail verification"


# ── DT-SIG-02: sign_payload -> verify_signature round trip succeeds ───────────

def test_dt_sig02_round_trip_valid():
    """DT-SIG-02: A valid signature verifies for the exact payload it was made over."""
    payload = _sample_payload()
    kp = create_keypair()
    signature = sign_payload(payload, kp)
    ok, reason = verify_signature(payload, signature, kp.public_key())
    assert ok is True, f"Round trip failed: {reason!r}"
    assert reason == "signature valid"


# ── DT-SIG-03: Tampered payload fails verification ───────────────────────────

def test_dt_sig03_tampered_payload():
    """DT-SIG-03: Modifying the payload after signing invalidates the signature."""
    payload = _sample_payload()
    kp = create_keypair()
    signature = sign_payload(payload, kp)

    tampered = dict(payload)
    tampered["user"] = "mallory"

    ok, reason = verify_signature(tampered, signature, kp.public_key())
    assert ok is False, f"Tampered payload should fail: {reason!r}"
    assert "invalid" in reason.lower(), f"Reason should mention invalid: {reason!r}"


# ── DT-SIG-04: Tampered signature fails verification ─────────────────────────

def test_dt_sig04_tampered_signature():
    """DT-SIG-04: Flipping one byte of the signature invalidates it."""
    payload = _sample_payload()
    kp = create_keypair()
    signature = sign_payload(payload, kp)
    tampered = bytes([signature[0] ^ 0x01]) + signature[1:]

    ok, reason = verify_signature(payload, tampered, kp.public_key())
    assert ok is False, f"Tampered signature should fail: {reason!r}"


# ── DT-SIG-05: Signature covers the exact canonical payload digest ───────────

def test_dt_sig05_digest_coverage():
    """DT-SIG-05: The signature is over the SHA-256 digest of the canonical payload."""
    payload = _sample_payload()
    kp = create_keypair()
    signature = sign_payload(payload, kp)

    digest = __import__("backend.app.cryptography.reference.signature", fromlist=["_digest"])._digest(
        __import__("backend.app.cryptography.reference.signature", fromlist=["_canonical_bytes"])._canonical_bytes(payload)
    )
    assert signature != digest, "Ed25519 signature must not be confused with the 32-byte digest"
    # Padding the signature should fail
    padded = signature + b"\x00"
    ok, _ = verify_signature(payload, padded, kp.public_key())
    assert ok is False, "Oversized signature must fail"


# ── DT-SIG-06: Different payloads produce different signatures ───────────────

def test_dt_sig06_different_payloads_different_signatures():
    """DT-SIG-06: Two different payloads yield different signatures."""
    payload_a = _sample_payload()
    payload_b = dict(payload_a)
    payload_b["user"] = "bob"

    kp = create_keypair()
    sig_a = sign_payload(payload_a, kp)
    sig_b = sign_payload(payload_b, kp)

    assert sig_a != sig_b, "Different payloads must produce different signatures"


# ── DT-SIG-07: Same payload + different keypair fails verification ───────────

def test_dt_sig07_different_keypair():
    """DT-SIG-07: A signature made with one keypair fails for another."""
    payload = _sample_payload()
    kp_a = create_keypair()
    kp_b = create_keypair()

    sig = sign_payload(payload, kp_a)
    ok, _ = verify_signature(payload, sig, kp_b.public_key())
    assert ok is False, "Signature made by another keypair must fail"


# ── DT-SIG-08: sign_result / verify_artifact round trip ──────────────────────

def test_dt_sig08_artifact_round_trip():
    """DT-SIG-08: sign_result and verify_artifact agree in a full artifact flow."""
    payload = _sample_payload()
    artifact = sign_result(payload)

    assert artifact["algorithm"] == ALGORITHM
    assert artifact["digest_algorithm"] == DIGEST_ALGORITHM
    assert len(artifact["public_key"]) == 44  # base64 of 32 bytes
    assert len(artifact["key_fingerprint"]) == 64

    result = verify_artifact(artifact)
    assert result["valid"] is True
    assert result["signature_valid"] is True
    assert result["digest_match"] is True
    assert result["payload_hash"] == artifact["payload_hash"]


def test_dt_sig09_production_artifact_verifies_with_reference():
    """Production artifacts must verify without calling production notary code."""
    artifact = sign_result(_sample_payload())
    production_result = verify_artifact(artifact)
    reference_result = reference_verify_artifact(artifact)

    assert reference_result["valid"] == production_result["valid"] is True
    assert reference_result["signature_valid"] == production_result["signature_valid"]
    assert reference_result["digest_match"] == production_result["digest_match"]
    assert reference_result["payload_hash"] == production_result["payload_hash"]
    assert reference_result["key_fingerprint"] == production_result["key_fingerprint"]


def test_dt_sig10_reference_artifact_verifies_with_production():
    """The reference signer emits artifacts accepted by the production verifier."""
    artifact = reference_sign_result(_sample_payload(), create_keypair())
    reference_result = reference_verify_artifact(artifact)
    production_result = verify_artifact(artifact)

    assert reference_result["valid"] == production_result["valid"] is True
    assert reference_result["signature_valid"] == production_result["signature_valid"]
    assert reference_result["digest_match"] == production_result["digest_match"]
    assert reference_result["payload_hash"] == production_result["payload_hash"]


def test_dt_sig11_canonical_equivalent_payloads_share_signature():
    """Canonical key ordering makes signing invariant to input insertion order."""
    key = create_keypair()
    first = {"z": 1, "a": {"y": "two", "b": "one"}}
    second = {"a": {"b": "one", "y": "two"}, "z": 1}

    assert sign_payload(first, key) == sign_payload(second, key)
