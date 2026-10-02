"""Cryptographic research notary — Ed25519 signatures over canonical result digests.

Workflow:
    experiment result -> canonical JSON -> SHA-256 digest -> Ed25519 signature
    anyone holding the exported artifact can verify offline:
        signature_valid  (public key verifies the signature)
        digest_match     (recomputed digest equals the recorded digest)

The signing key lives under ``results/notary/`` and is a DEMO key for this research
prototype — not a production PKI.  Public key is exported alongside every artifact
so verification needs nothing from this server.
"""
from __future__ import annotations

import base64
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from backend.app.core.config import settings
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.versioning import (
    CRYPTOGRAPHIC_PROTOCOL_VERSION,
    RESEARCH_ARTIFACT_VERSION,
    SCHEMA_VERSION,
    SUPPORTED_CRYPTOGRAPHIC_PROTOCOL_VERSIONS,
    SUPPORTED_RESEARCH_ARTIFACT_VERSIONS,
    SUPPORTED_SCHEMA_VERSIONS,
)

NOTARY_DIR = Path(settings.RESULTS_DIR) / "notary"
PRIVATE_KEY_FILE = "notary_private_key.pem"
PUBLIC_KEY_FILE = "notary_public_key.pem"

ALGORITHM = "Ed25519"
DIGEST_ALGORITHM = "SHA-256"


def _digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _canonical_bytes(payload: Dict[str, Any]) -> bytes:
    return canonicalize(payload).encode("utf-8")


def ensure_keypair() -> Path:
    """Create the demo Ed25519 keypair if absent; return the private key path."""
    NOTARY_DIR.mkdir(parents=True, exist_ok=True)
    private_path = NOTARY_DIR / PRIVATE_KEY_FILE
    public_path = NOTARY_DIR / PUBLIC_KEY_FILE
    if not private_path.exists():
        key = Ed25519PrivateKey.generate()
        private_path.write_bytes(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        try:
            private_path.chmod(0o600)
        except OSError:  # pragma: no cover — best effort on Windows
            pass
        public_path.write_bytes(
            key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
    return private_path


def _load_private_key() -> Ed25519PrivateKey:
    pem = ensure_keypair().read_bytes()
    return serialization.load_pem_private_key(pem, password=None)


def public_key_b64() -> str:
    """Base64 of the raw 32-byte public key (portable inside JSON artifacts)."""
    key = _load_private_key().public_key()
    raw = key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode("ascii")


def fingerprint(public_key_b64_value: Optional[str] = None) -> str:
    """SHA-256 fingerprint of a raw public key (defaults to the local notary key)."""
    raw = (
        base64.b64decode(public_key_b64_value, validate=True)
        if public_key_b64_value
        else base64.b64decode(public_key_b64())
    )
    return hashlib.sha256(raw).hexdigest()


def sign_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sign a research payload; returns a self-contained verifiable artifact."""
    digest = _digest(_canonical_bytes(payload))
    signature = _load_private_key().sign(digest)
    return {
        "artifact_type": f"sentinelcrypt.research-artifact.v{RESEARCH_ARTIFACT_VERSION}",
        "protocol_version": CRYPTOGRAPHIC_PROTOCOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "research_artifact_version": RESEARCH_ARTIFACT_VERSION,
        "payload": payload,
        "payload_hash": digest.hex(),
        "digest_algorithm": DIGEST_ALGORITHM,
        "signature": base64.b64encode(signature).decode("ascii"),
        "algorithm": ALGORITHM,
        "public_key": public_key_b64(),
        "key_fingerprint": fingerprint(),
        "signed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def verify_artifact(artifact: Dict[str, Any]) -> Dict[str, Any]:
    """Verify an exported artifact offline-style: digest match + signature check."""
    if not isinstance(artifact, dict):
        return {
            "valid": False,
            "signature_valid": False,
            "digest_match": False,
            "reason": "Artifact must be a JSON object.",
        }
    versions = (
        ("protocol_version", SUPPORTED_CRYPTOGRAPHIC_PROTOCOL_VERSIONS),
        ("schema_version", SUPPORTED_SCHEMA_VERSIONS),
        ("research_artifact_version", SUPPORTED_RESEARCH_ARTIFACT_VERSIONS),
    )
    for field, supported in versions:
        if field not in artifact:
            version = 1
        else:
            value = artifact[field]
            if isinstance(value, bool) or not isinstance(value, (int, str)):
                version = repr(value)
            else:
                try:
                    version = int(value)
                except ValueError:
                    version = value
        if version not in supported:
            return {
                "valid": False,
                "signature_valid": False,
                "digest_match": False,
                "reason": (
                    f"Unsupported {field}={version} "
                    f"(this verifier supports: {', '.join(map(str, sorted(supported)))})."
                ),
            }

    artifact_type = artifact.get("artifact_type")
    expected_type = (
        f"sentinelcrypt.research-artifact.v{RESEARCH_ARTIFACT_VERSION}"
    )
    if "artifact_type" in artifact and artifact_type != expected_type:
        return {
            "valid": False,
            "signature_valid": False,
            "digest_match": False,
            "reason": f"Unsupported artifact_type={artifact_type!r}.",
        }

    required = {"payload", "payload_hash", "signature", "public_key"}
    missing = sorted(required - set(artifact or {}))
    if missing:
        return {
            "valid": False,
            "signature_valid": False,
            "digest_match": False,
            "reason": f"Artifact missing required fields: {', '.join(missing)}.",
        }
    try:
        digest = _digest(_canonical_bytes(artifact["payload"]))
    except Exception as exc:
        return {
            "valid": False,
            "signature_valid": False,
            "digest_match": False,
            "reason": f"Payload is not canonically serializable: {exc}",
        }
    digest_match = digest.hex() == artifact["payload_hash"]

    try:
        public_raw = base64.b64decode(artifact["public_key"], validate=True)
        public_key = Ed25519PublicKey.from_public_bytes(public_raw)
        public_key.verify(base64.b64decode(artifact["signature"]), digest)
        signature_valid = True
        reason = "Signature verified against the artifact's own public key."
    except (InvalidSignature, ValueError, TypeError) as exc:
        signature_valid = False
        reason = f"Signature verification failed: {exc.__class__.__name__}."

    if signature_valid and not digest_match:
        reason = "Signature valid but recorded payload_hash does not match the payload."
    return {
        "valid": bool(signature_valid and digest_match),
        "signature_valid": signature_valid,
        "digest_match": digest_match,
        "payload_hash": digest.hex(),
        "recorded_hash": artifact["payload_hash"],
        "algorithm": artifact.get("algorithm", ALGORITHM),
        "key_fingerprint": (
            # fingerprint of the key the artifact was actually signed with
            fingerprint(artifact["public_key"]) if signature_valid else None
        ),
        "signed_by_notary": (
            signature_valid and fingerprint(artifact["public_key"]) == fingerprint()
        ),
        "reason": reason,
        "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
