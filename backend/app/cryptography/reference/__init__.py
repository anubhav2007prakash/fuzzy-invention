"""Readable reference implementation for SentinelCrypt's evidence protocol.

Production code does not import this package. Deterministic hashing helpers
are pure; key generation and timestamps are intentionally nondeterministic.
"""

from backend.app.cryptography.reference.canonical import canonicalize
from backend.app.cryptography.reference.digest import sha256_bytes, sha256_hex
from backend.app.cryptography.reference.chain import (
    GENESIS,
    build_chain,
    payload_hash,
    record_hash,
    verify_chain,
    verify_record,
)
from backend.app.cryptography.reference.verify import verify_ledger
from backend.app.cryptography.reference.signature import (
    create_keypair,
    sign_result,
    sign_payload,
    verify_artifact,
    verify_signature,
)
from backend.app.cryptography.reference.merkle import (
    MerkleTree,
    leaf_hash,
    node_hash,
    verify_membership,
)

# Convenience aliases matching import names used in differential test modules.
ref_canonical_json = canonicalize
ref_sha256_hex = sha256_hex
ref_payload_hash = payload_hash
ref_record_hash = record_hash

__all__ = [
    # canonical + digest
    "canonicalize",
    "sha256_hex",
    "sha256_bytes",
    # chain
    "GENESIS",
    "payload_hash",
    "record_hash",
    "build_chain",
    "verify_chain",
    "verify_record",
    "verify_ledger",
    # signature
    "create_keypair",
    "sign_result",
    "sign_payload",
    "verify_artifact",
    "verify_signature",
    # merkle
    "MerkleTree",
    "leaf_hash",
    "node_hash",
    "verify_membership",
    # aliases
    "ref_canonical_json",
    "ref_sha256_hex",
    "ref_payload_hash",
    "ref_record_hash",
]
