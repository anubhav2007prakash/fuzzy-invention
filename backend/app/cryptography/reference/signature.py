"""Readable Ed25519 reference for SentinelCrypt's signed research artifacts.

This module uses the standard ``cryptography`` Ed25519 implementation, but
does not call the production notary. It intentionally keeps artifact signing
and verification explicit so tests can compare the two implementations.
"""

from __future__ import annotations

import base64
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from backend.app.cryptography.reference.canonical import canonicalize

__all__ = [
    "ALGORITHM",
    "DIGEST_ALGORITHM",
    "create_keypair",
    "export_keypair",
    "load_keypair",
    "sign_payload",
    "verify_signature",
    "public_key_b64",
    "fingerprint",
    "sign_result",
    "verify_artifact",
]

ALGORITHM = "Ed25519"
DIGEST_ALGORITHM = "SHA-256"
PROTOCOL_VERSION = 1
SCHEMA_VERSION = 1
RESEARCH_ARTIFACT_VERSION = 1


def _canonical_bytes(payload: Any) -> bytes:
    """Return the protocol's canonical JSON encoded as UTF-8."""
    return canonicalize(payload).encode("utf-8")


def _digest(data: bytes) -> bytes:
    """Compute the protocol's standard SHA-256 digest."""
    return hashlib.sha256(data).digest()


def create_keypair() -> Ed25519PrivateKey:
    """Generate an Ed25519 key for tests or research examples."""
    return Ed25519PrivateKey.generate()


def export_keypair(
    private_key: Ed25519PrivateKey, public_path: str, private_path: str
) -> None:
    """Write PEM-encoded keys; private-key files are unencrypted demo material."""
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    for path, content in ((public_path, public_bytes), (private_path, private_bytes)):
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)


def load_keypair(private_path: str) -> Ed25519PrivateKey:
    """Load an unencrypted PEM-encoded Ed25519 private key."""
    key = serialization.load_pem_private_key(
        Path(private_path).read_bytes(), password=None
    )
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("The PEM file does not contain an Ed25519 private key.")
    return key


def public_key_b64(public_key: Ed25519PublicKey) -> str:
    """Encode a raw Ed25519 public key as base64."""
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode("ascii")


def fingerprint(public_key_b64_value: str) -> str:
    """Return the SHA-256 fingerprint of a base64-encoded raw public key."""
    raw = base64.b64decode(public_key_b64_value, validate=True)
    return hashlib.sha256(raw).hexdigest()


def sign_payload(payload: Any, private_key: Ed25519PrivateKey) -> bytes:
    """Sign SHA-256(canonical-json-UTF8(payload)) using Ed25519."""
    return private_key.sign(_digest(_canonical_bytes(payload)))


def verify_signature(
    payload: Any, signature: bytes, public_key: Ed25519PublicKey
) -> Tuple[bool, str]:
    """Verify a signature over the canonical payload digest."""
    digest = _digest(_canonical_bytes(payload))
    try:
        public_key.verify(signature, digest)
    except InvalidSignature:
        return False, "signature invalid: digest mismatch"
    return True, "signature valid"


def sign_result(
    payload: Dict[str, Any],
    private_key: Optional[Ed25519PrivateKey] = None,
) -> Dict[str, Any]:
    """Create a versioned artifact using the supplied or a fresh research key."""
    key = private_key or create_keypair()
    public_key = key.public_key()
    digest = _digest(_canonical_bytes(payload))
    public_key_value = public_key_b64(public_key)
    return {
        "artifact_type": f"sentinelcrypt.research-artifact.v{RESEARCH_ARTIFACT_VERSION}",
        "protocol_version": PROTOCOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "research_artifact_version": RESEARCH_ARTIFACT_VERSION,
        "payload": payload,
        "payload_hash": digest.hex(),
        "digest_algorithm": DIGEST_ALGORITHM,
        "signature": base64.b64encode(key.sign(digest)).decode("ascii"),
        "algorithm": ALGORITHM,
        "public_key": public_key_value,
        "key_fingerprint": fingerprint(public_key_value),
        "signed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def verify_artifact(artifact: Dict[str, Any]) -> Dict[str, Any]:
    """Verify an artifact's supported version, digest, and Ed25519 signature."""
    if not isinstance(artifact, dict):
        return {
            "valid": False,
            "signature_valid": False,
            "digest_match": False,
            "reason": "Artifact must be a JSON object.",
        }

    versions = (
        ("protocol_version", PROTOCOL_VERSION),
        ("schema_version", SCHEMA_VERSION),
        ("research_artifact_version", RESEARCH_ARTIFACT_VERSION),
    )
    for field, supported_version in versions:
        value = artifact.get(field, 1)
        try:
            version = int(value) if not isinstance(value, bool) else value
        except (TypeError, ValueError):
            version = value
        if version != supported_version:
            return {
                "valid": False,
                "signature_valid": False,
                "digest_match": False,
                "reason": f"Unsupported {field}={version!r}.",
            }

    expected_type = f"sentinelcrypt.research-artifact.v{RESEARCH_ARTIFACT_VERSION}"
    if artifact.get("artifact_type", expected_type) != expected_type:
        return {
            "valid": False,
            "signature_valid": False,
            "digest_match": False,
            "reason": f"Unsupported artifact_type={artifact.get('artifact_type')!r}.",
        }

    required = {"payload", "payload_hash", "signature", "public_key"}
    missing = sorted(required - artifact.keys())
    if missing:
        return {
            "valid": False,
            "signature_valid": False,
            "digest_match": False,
            "reason": f"Artifact missing required fields: {', '.join(missing)}.",
        }

    try:
        digest = _digest(_canonical_bytes(artifact["payload"]))
    except (TypeError, ValueError) as exc:
        return {
            "valid": False,
            "signature_valid": False,
            "digest_match": False,
            "reason": f"Payload is not canonically serializable: {exc}",
        }

    recorded_hash = artifact["payload_hash"]
    digest_match = isinstance(recorded_hash, str) and digest.hex() == recorded_hash
    try:
        raw_public_key = base64.b64decode(artifact["public_key"], validate=True)
        public_key = Ed25519PublicKey.from_public_bytes(raw_public_key)
        signature = base64.b64decode(artifact["signature"], validate=True)
        public_key.verify(signature, digest)
        signature_valid = True
        reason = "Signature verified against the artifact's own public key."
    except (InvalidSignature, TypeError, ValueError) as exc:
        signature_valid = False
        reason = f"Signature verification failed: {exc.__class__.__name__}."

    if signature_valid and not digest_match:
        reason = "Signature valid but recorded payload_hash does not match the payload."
    return {
        "valid": bool(signature_valid and digest_match),
        "signature_valid": signature_valid,
        "digest_match": digest_match,
        "payload_hash": digest.hex(),
        "recorded_hash": recorded_hash,
        "algorithm": artifact.get("algorithm", ALGORITHM),
        "key_fingerprint": fingerprint(artifact["public_key"]) if signature_valid else None,
        "reason": reason,
    }
