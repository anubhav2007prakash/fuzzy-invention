"""Merkle tree — second integrity architecture for comparison against the hash chain.

Domain separation: leaves are H(0x01 || data), interior nodes H(0x00 || l || r),
so a leaf hash can never be reinterpreted as an interior node (second-preimage).
Odd nodes at a level are duplicated, the standard Bitcoin/RFC-style convention.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Sequence

from backend.app.cryptography.canonicalization import canonicalize

LEAF_PREFIX = b"\x01"
NODE_PREFIX = b"\x00"
DIGEST_BYTES = 32


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def leaf_hash(payload: Any) -> bytes:
    """H(0x01 || canonical(payload)) for any JSON-able payload."""
    raw = payload if isinstance(payload, (bytes, bytearray)) else canonicalize(payload).encode("utf-8")
    return _sha256(LEAF_PREFIX + raw)


def node_hash(left: bytes, right: bytes) -> bytes:
    """H(0x00 || left || right) for interior nodes."""
    return _sha256(NODE_PREFIX + left + right)


class MerkleTree:
    """Build-once Merkle tree with inclusion proofs."""

    def __init__(self, leaves: Sequence[Any]):
        if not leaves:
            raise ValueError("MerkleTree requires at least one leaf.")
        level: List[bytes] = [
            leaf if isinstance(leaf, (bytes, bytearray)) else leaf_hash(leaf)
            for leaf in leaves
        ]
        self._levels: List[List[bytes]] = [level]
        while len(level) > 1:
            if len(level) % 2 == 1:
                level = level + [level[-1]]
            level = [
                node_hash(level[i], level[i + 1]) for i in range(0, len(level), 2)
            ]
            self._levels.append(level)

    @property
    def root(self) -> str:
        return self._levels[-1][0].hex()

    @property
    def n_leaves(self) -> int:
        return len(self._levels[0])

    @property
    def depth(self) -> int:
        return len(self._levels) - 1

    @property
    def n_nodes(self) -> int:
        return sum(len(level) for level in self._levels)

    @property
    def storage_bytes(self) -> int:
        """Raw digest bytes required to persist every node."""
        return self.n_nodes * DIGEST_BYTES

    def proof(self, index: int) -> List[Dict[str, str]]:
        """Sibling path proving leaf `index` is in the tree under `root`."""
        if not 0 <= index < self.n_leaves:
            raise IndexError(f"Leaf index {index} out of range (n={self.n_leaves}).")
        path: List[Dict[str, str]] = []
        idx = index
        for level in self._levels[:-1]:
            if idx % 2 == 0:
                sib = idx + 1 if idx + 1 < len(level) else idx
                position = "right" if sib != idx else "dup"
            else:
                sib = idx - 1
                position = "left"
            path.append({"sibling": level[sib].hex(), "position": position})
            idx //= 2
        return path

    @staticmethod
    def verify_proof(leaf: bytes, proof: Sequence[Dict[str, str]], root: str) -> bool:
        """Recompute the root from a leaf + sibling path and compare."""
        current = leaf
        for step in proof:
            sibling = bytes.fromhex(step["sibling"])
            if step["position"] == "left":
                current = node_hash(sibling, current)
            elif step["position"] == "dup":
                current = node_hash(current, current)
            else:
                current = node_hash(current, sibling)
        return current.hex() == root

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root": self.root,
            "n_leaves": self.n_leaves,
            "depth": self.depth,
            "n_nodes": self.n_nodes,
            "storage_bytes": self.storage_bytes,
            "hash_algorithm": "SHA-256 with leaf/node domain separation",
        }
