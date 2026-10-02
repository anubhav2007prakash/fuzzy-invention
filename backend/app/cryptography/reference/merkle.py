"""Merkle tree for the SentinelCrypt second integrity architecture.

Reference implementation of ``backend.app.cryptography.merkle``.
Domain separation: leaves are  ``H(0x01 || data)``, interior nodes are
``H(0x00 || left || right)``.  This prevents a leaf hash from being
reinterpreted as an interior node (second-preimage resistance).

Protocol
--------
1. leaf_hash(payload)  = SHA-256(0x01 || canonical(payload))
2. node_hash(left, right) = SHA-256(0x00 || left || right)
3. root = the single top node.
4. membership proof: sibling path with labels 'left'/'right'/'dup'.
5. verify_membership(leaf_bytes, proof, root) => bool.

Performance is intentionally ignored; clarity is the priority.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from backend.app.cryptography.reference.canonical import canonicalize
from backend.app.cryptography.reference.digest import sha256_hex

__all__ = ["MerkleTree", "leaf_hash", "node_hash", "verify_membership"]

LEAF_PREFIX = b"\x01"
NODE_PREFIX = b"\x00"


def leaf_hash(payload: Any) -> str:
    """Leaf: SHA-256(0x01 || canonical(payload)).  Returns lowercase hex.

    Mirrors the production implementation: a ``str`` payload is treated as a
    JSON value (canonicalized), while bytes/bytearray are used raw.
    """
    if isinstance(payload, (bytes, bytearray)):
        # Raw bytes leaf: H(0x01 || payload) with no canonicalization.
        raw = bytes(payload)
    else:
        # Any other JSON-able value is canonicalized first.
        raw = canonicalize(payload).encode("utf-8")
    return sha256_hex(LEAF_PREFIX + raw)


def node_hash(left: str, right: str) -> str:
    """Interior node: SHA-256(0x00 || left || right).  Both sides are hex."""
    return sha256_hex(NODE_PREFIX + bytes.fromhex(left) + bytes.fromhex(right))


class MerkleTree:
    """Build-once tree with the production API's leaf-input convention.

    JSON values are hashed with ``leaf_hash``. Byte values are already-hashed
    leaf digests, matching ``backend.app.cryptography.merkle.MerkleTree``.
    """

    def __init__(self, leaves: Sequence[Any]):
        if not leaves:
            raise ValueError("MerkleTree requires at least one leaf.")
        def _to_hex(value: Any) -> str:
            if isinstance(value, (bytes, bytearray)):
                return bytes(value).hex()
            return leaf_hash(value)

        level = [_to_hex(leaf) for leaf in leaves]
        self._levels: List[List[str]] = [level]
        while len(level) > 1:
            if len(level) % 2 == 1:
                level = level + [level[-1]]  # duplicate the last node (Bitcoin/RFC style)
            level = [node_hash(level[i], level[i + 1]) for i in range(0, len(level), 2)]
            self._levels.append(level)

    @property
    def root(self) -> str:
        """Hex digest of the root node."""
        return self._levels[-1][0]

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
        return self.n_nodes * 32

    def proof(self, index: int) -> List[Dict[str, str]]:
        """Return a sibling-path proof that leaf ``index`` is in the tree."""
        if not 0 <= index < self.n_leaves:
            raise IndexError(
                f"Leaf index {index} out of range (n={self.n_leaves})."
            )
        path: List[Dict[str, str]] = []
        idx = index
        for level in self._levels[:-1]:
            if idx % 2 == 0:
                sibling = idx + 1 if idx + 1 < len(level) else idx
                position = "right" if sibling != idx else "dup"
            else:
                sibling = idx - 1
                position = "left"
            path.append({"sibling": level[sibling], "position": position})
            idx //= 2
        return path

    @staticmethod
    def verify_membership(leaf: bytes, proof: Sequence[Dict[str, str]], root: str) -> bool:
        """Recompute the root from a leaf + sibling path and compare to the claimed root."""
        current = sha256_hex(LEAF_PREFIX + leaf)
        for step in proof:
            sibling = step["sibling"]
            if step["position"] == "left":
                current = node_hash(sibling, current)
            elif step["position"] == "dup":
                current = node_hash(current, current)
            else:
                current = node_hash(current, sibling)
        return current == root


def verify_membership(leaf: bytes, proof: Sequence[Dict[str, str]], root: str) -> bool:
    """Standalone convenience function for the membership check."""
    return MerkleTree.verify_membership(leaf, proof, root)
