"""Tests for the Merkle tree (EXP-G foundation)."""
import pytest

from backend.app.cryptography.merkle import MerkleTree, leaf_hash, node_hash


def _leaves(n):
    return [{"i": i, "value": f"payload-{i}"} for i in range(n)]


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 7, 8, 16])
def test_all_proofs_verify(n):
    leaves = _leaves(n)
    tree = MerkleTree(leaves)
    for i in range(n):
        proof = tree.proof(i)
        assert MerkleTree.verify_proof(leaf_hash(leaves[i]), proof, tree.root)


def test_tampered_payload_changes_root_and_fails_proof():
    leaves = _leaves(8)
    tree = MerkleTree(leaves)
    original_root = tree.root

    tampered = list(leaves)
    tampered[3] = {"i": 3, "value": "payload-CHANGED"}
    tampered_tree = MerkleTree(tampered)

    assert tampered_tree.root != original_root
    # the ORIGINAL tree's proof for index 3 must fail for the TAMPERED leaf
    assert not MerkleTree.verify_proof(
        leaf_hash(tampered[3]), tree.proof(3), original_root
    )
    # and the original leaf still verifies against the original root
    assert MerkleTree.verify_proof(
        leaf_hash(leaves[3]), tree.proof(3), original_root
    )


def test_omission_changes_root():
    leaves = _leaves(8)
    root = MerkleTree(leaves).root
    omitted = leaves[:4] + leaves[5:]
    assert MerkleTree(omitted).root != root


def test_domain_separation_leaf_nequals_node():
    data = b"same-bytes"
    assert leaf_hash(data) != node_hash(data, data)
    # leaf hash is deterministic
    assert leaf_hash(data) == leaf_hash(data)


def test_odd_leaf_count_duplicate_handling():
    tree = MerkleTree(_leaves(5))
    assert tree.depth == 3  # 5 -> 6 -> 3 -> 2 -> 1... (dup rules)
    assert tree.n_leaves == 5
    assert MerkleTree.verify_proof(
        leaf_hash(_leaves(5)[4]), tree.proof(4), tree.root
    )


def test_empty_tree_rejected_and_bad_index():
    with pytest.raises(ValueError):
        MerkleTree([])
    tree = MerkleTree(_leaves(4))
    with pytest.raises(IndexError):
        tree.proof(9)


def test_storage_metrics():
    tree = MerkleTree(_leaves(8))
    assert tree.storage_bytes == tree.n_nodes * 32
    assert tree.to_dict()["root"] == tree.root
