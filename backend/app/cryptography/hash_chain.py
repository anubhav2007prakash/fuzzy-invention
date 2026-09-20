"""Forward-Linked Cryptographic Hash Chain Implementation."""
from typing import Dict, Any
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hashing import sha256_hash

GENESIS_PREVIOUS_HASH = "0" * 64

def calculate_payload_hash(payload: Dict[str, Any]) -> str:
    """Compute SHA-256 hash of canonicalized JSON payload."""
    canonical_str = canonicalize(payload)
    return sha256_hash(canonical_str)

def calculate_record_hash(previous_hash: str, payload_hash: str) -> str:
    """
    Compute forward-linked record hash:
    RecordHash = SHA-256(previous_hash + payload_hash)
    """
    material = previous_hash + payload_hash
    return sha256_hash(material)

def build_audit_record_hashes(payload: Dict[str, Any], previous_hash: str = GENESIS_PREVIOUS_HASH) -> tuple[str, str, str]:
    """
    Given a payload and previous record hash, compute:
    - canonical JSON string
    - payload hash
    - forward-linked record hash
    """
    canonical_payload = canonicalize(payload)
    payload_hash = sha256_hash(canonical_payload)
    record_hash = calculate_record_hash(previous_hash, payload_hash)
    return canonical_payload, payload_hash, record_hash
