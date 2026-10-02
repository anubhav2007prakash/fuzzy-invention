"""Differential tests — Merkle tree (reference package).

Compares the production Merkle tree (backend.app.cryptography.merkle)
against the clean reference implementation (backend.app.cryptography.reference.merkle).

Protocol
--------
1. leaf_hash(payload)  = SHA-256(0x01 || canonical(payload))
2. node_hash(left, right) = SHA-256(0x00 || left || right)
3. root = the single top node.
4. membership proof: sibling path with labels 'left'/'right'/'dup'.
5. verify_membership(leaf_bytes, proof, root) => bool.

Domain separation (leaf 0x01, interior 0x00) prevents a leaf hash from being
reinterpreted as an interior node.  Odd nodes at a level are duplicated (the
standard Bitcoin/RFC-style convention).

Component: merkle
Tests:
  DT-MERKLE-01  leaf_hash returns a 64-char lowercase hex digest
  DT-MERKLE-02  leaf_hash is deterministic
  DT-MERKLE-03  node_hash is deterministic and 64-char hex
  DT-MERKLE-04  MerkleTree.root matches the hand-computed root
  DT-MERKLE-05  proof() returns a valid sibling path
  DT-MERKLE-06  verify_membership accepts a correct proof
  DT-MERKLE-07  tampered proof / sibling fails verification
  DT-MERKLE-08  membership is order-independent (tree with n leaves)
  DT-MERKLE-09  storage_bytes and depth match the tree shape
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.cryptography.merkle import (
    MerkleTree,
    leaf_hash as prod_leaf_hash,
    node_hash as prod_node_hash,
)
from backend.app.cryptography.reference.merkle import (
    MerkleTree as RefMerkleTree,
    leaf_hash as ref_leaf_hash,
    node_hash as ref_node_hash,
    verify_membership as ref_verify_membership,
)
from backend.app.cryptography.reference.canonical import canonicalize

# ── Helpers ───────────────────────────────────────────────────────────────────

def _ref_leaf_hash(payload: Any) -> str:
    """Independent reference leaf hash: SHA-256(0x01 || canonical(payload))."""
    import hashlib
    if isinstance(payload, (bytes, bytearray)):
        raw = bytes(payload)
    else:
        raw = canonicalize(payload).encode("utf-8")
    return hashlib.sha256(b"\x01" + raw).hexdigest()


# ── DT-MERKLE-01: leaf_hash returns a 64-char lowercase hex digest ────────────

@pytest.mark.parametrize("payload", [
    {"a": 1},
    "string-leaf",
    42,
    [1, 2, 3],
    b"raw-bytes",
])
def test_dt_merkle01_leaf_hash_format(payload):
    """DT-MERKLE-01: leaf_hash returns a 64-char lowercase hex digest."""
    result = ref_leaf_hash(payload)
    assert isinstance(result, str)
    assert len(result) == 64
    assert result == result.lower()
    assert all(c in "0123456789abcdef" for c in result)


# ── DT-MERKLE-02: leaf_hash is deterministic ──────────────────────────────────

@pytest.mark.parametrize("payload", [
    {"nested": {"deep": "value"}},
    "unicode-leaf",
    3.14,
])
def test_dt_merkle02_leaf_hash_deterministic(payload):
    """DT-MERKLE-02: leaf_hash is deterministic."""
    first = ref_leaf_hash(payload)
    second = ref_leaf_hash(payload)
    assert first == second, f"Non-deterministic leaf_hash for {payload!r}"


# ── DT-MERKLE-03: node_hash is deterministic and 64-char hex ──────────────────

def test_dt_merkle03_node_hash():
    """DT-MERKLE-03: node_hash is deterministic and 64-char lowercase hex."""
    left = "a" * 64
    right = "b" * 64
    first = ref_node_hash(left, right)
    second = ref_node_hash(left, right)
    assert first == second
    assert len(first) == 64
    assert first == first.lower()
    assert all(c in "0123456789abcdef" for c in first)


# ── DT-MERKLE-04: MerkleTree.root matches the hand-computed root ─────────────

@pytest.mark.parametrize("leaves", [
    [{"a": 1}],
    [{"a": 1}, {"b": 2}],
    [{"a": 1}, {"b": 2}, {"c": 3}],
    [{"a": 1}, {"b": 2}, {"c": 3}, {"d": 4}],
])
def test_dt_merkle04_root_matches_hand_computed(leaves):
    """DT-MERKLE-04: MerkleTree.root matches a manual node_hash chain."""
    ref_tree = RefMerkleTree(leaves)

    # Build the same tree by hand
    level = [ref_leaf_hash(l) for l in leaves]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level = level + [level[-1]]
        level = [ref_node_hash(level[i], level[i + 1]) for i in range(0, len(level), 2)]

    assert ref_tree.root == level[0], (
        f"[DT-MERKLE-04] Root mismatch: tree={ref_tree.root}, hand={level[0]}"
    )


# ── DT-MERKLE-05: proof() returns a valid sibling path ────────────────────────

@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8])
def test_dt_merkle05_proof_returns_valid_path(n):
    """DT-MERKLE-05: proof(index) returns a list of sibling steps for each leaf."""
    tree = RefMerkleTree([{"i": i} for i in range(n)])
    for idx in range(n):
        path = tree.proof(idx)
        assert isinstance(path, list)
        assert all(isinstance(step, dict) and "sibling" in step and "position" in step for step in path)


# ── DT-MERKLE-06: verify_membership accepts a correct proof ───────────────────

@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8, 16])
def test_dt_merkle06_verify_membership_accepts_correct_proof(n):
    """DT-MERKLE-06: verify_membership succeeds for a valid sibling path."""
    payloads = [{"i": i} for i in range(n)]
    tree = RefMerkleTree(payloads)

    for idx, payload in enumerate(payloads):
        leaf_bytes = canonicalize(payload).encode("utf-8")
        proof = tree.proof(idx)
        ok = ref_verify_membership(leaf_bytes, proof, tree.root)
        assert ok is True, f"Membership verification failed for leaf {idx}"


# ── DT-MERKLE-07: tampered proof / sibling fails verification ────────────────

@pytest.mark.parametrize("n", [2, 4, 8])
def test_dt_merkle07_tampered_proof_fails(n):
    """DT-MERKLE-07: A tampered sibling or position breaks membership verification."""
    payloads = [{"i": i} for i in range(n)]
    tree = RefMerkleTree(payloads)

    for idx in range(n):
        leaf_bytes = canonicalize(payloads[idx]).encode("utf-8")
        proof = list(tree.proof(idx))

        # Tamper with the first sibling
        tampered = [{"sibling": "0" * 64, "position": "right"}]
        assert ref_verify_membership(leaf_bytes, tampered, tree.root) is False

        # Tamper with the first position: flip to a *different* value so the
        # recomputed root changes.
        expected_position = proof[0]["position"]
        tampered_position = "right" if expected_position == "left" else "left"
        tampered2 = [{"sibling": proof[0]["sibling"], "position": tampered_position}]
        assert ref_verify_membership(leaf_bytes, tampered2, tree.root) is False


# ── DT-MERKLE-08: proofs are deterministic for a fixed leaf order ─────────────

def test_dt_merkle08_stable_proofs():
    """DT-MERKLE-08: Proofs for a fixed tree are deterministic and verify."""
    payloads = [{"a": 1}, {"b": 2}, {"c": 3}]
    tree = RefMerkleTree(payloads)

    for idx, payload in enumerate(payloads):
        leaf_bytes = canonicalize(payload).encode("utf-8")
        proof = tree.proof(idx)
        assert proof is not None
        assert all(isinstance(step, dict) and "sibling" in step and "position" in step for step in proof)

        assert ref_verify_membership(leaf_bytes, proof, tree.root) is True, (
            f"Proof for leaf {idx} did not verify"
        )

    # Proof of a different leaf must verify under the same root
    leaf_bytes = canonicalize(payloads[2]).encode("utf-8")
    proof = tree.proof(2)
    assert ref_verify_membership(leaf_bytes, proof, tree.root) is True


# ── DT-MERKLE-09: storage_bytes and depth match the tree shape ───────────────

@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8])
def test_dt_merkle09_shape_properties(n):
    """DT-MERKLE-09: depth and storage_bytes match the tree shape."""
    tree = RefMerkleTree([{"i": i} for i in range(n)])

    # Depth equals the number of levels beyond the leaf level.
    assert tree.depth == len(tree._levels) - 1, (
        f"depth: {tree.depth} != len(_levels)-1 = {len(tree._levels) - 1}"
    )

    # n_nodes and storage_bytes
    assert tree.n_leaves == n
    assert tree.n_nodes >= n
    assert tree.storage_bytes == tree.n_nodes * 32


# ── DT-MERKLE-10: standalone verify_membership matches MerkleTree method ──────

def test_dt_merkle10_verify_membership_standalone_matches_class():
    """DT-MERKLE-10: the standalone verify_membership equals the class method."""
    payloads = [{"a": 1}, {"b": 2}, {"c": 3}]
    tree = RefMerkleTree(payloads)

    for idx, payload in enumerate(payloads):
        leaf_bytes = canonicalize(payload).encode("utf-8")
        proof = tree.proof(idx)
        via_class = tree.verify_membership(leaf_bytes, proof, tree.root)
        via_standalone = ref_verify_membership(leaf_bytes, proof, tree.root)
        assert via_class is True
        assert via_standalone is True
        assert via_class == via_standalone


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8, 13])
def test_dt_merkle11_production_and_reference_match(n):
    """Compare roots, paths, and proof outcomes across both implementations."""
    payloads = [{"index": index, "value": f"leaf-{index}"} for index in range(n)]
    production_tree = MerkleTree(payloads)
    reference_tree = RefMerkleTree(payloads)

    for payload in payloads:
        assert prod_leaf_hash(payload).hex() == ref_leaf_hash(payload)
    assert production_tree.root == reference_tree.root
    assert production_tree.n_leaves == reference_tree.n_leaves
    assert production_tree.depth == reference_tree.depth
    assert production_tree.n_nodes == reference_tree.n_nodes
    assert production_tree.storage_bytes == reference_tree.storage_bytes

    for index, payload in enumerate(payloads):
        production_proof = production_tree.proof(index)
        reference_proof = reference_tree.proof(index)
        assert production_proof == reference_proof, (
            f"Merkle proof mismatch for n={n}, index={index}: "
            f"production={production_proof!r}, reference={reference_proof!r}"
        )

        production_valid = production_tree.verify_proof(
            production_tree._levels[0][index], production_proof, production_tree.root
        )
        reference_valid = ref_verify_membership(
            canonicalize(payload).encode("utf-8"),
            reference_proof,
            reference_tree.root,
        )
        assert production_valid == reference_valid is True, (
            f"Merkle proof result mismatch for n={n}, index={index}: "
            f"production={production_valid}, reference={reference_valid}"
        )

    if n >= 2:
        production_parent = prod_node_hash(
            prod_leaf_hash(payloads[0]), prod_leaf_hash(payloads[1])
        ).hex()
        reference_parent = ref_node_hash(
            ref_leaf_hash(payloads[0]), ref_leaf_hash(payloads[1])
        )
        assert production_parent == reference_parent


def test_dt_merkle12_prehashed_byte_leaves_match_production_convention():
    leaves = [bytes.fromhex("11" * 32), bytes.fromhex("22" * 32)]
    production_tree = MerkleTree(leaves)
    reference_tree = RefMerkleTree(leaves)

    assert production_tree.root == reference_tree.root
    assert production_tree.proof(0) == reference_tree.proof(0)
