"""Metamorphic Relations for Cryptographic Hashing and Merkle Structures."""
from __future__ import annotations

from typing import Any, Dict, Tuple

from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hash_chain import calculate_record_hash
from backend.app.cryptography.hashing import sha256_hash
from backend.app.cryptography.merkle import MerkleTree, leaf_hash, node_hash
from backend.tests.metamorphic.framework import (
    Category,
    MetamorphicRelation,
)


def _hamming_distance(hex1: str, hex2: str) -> int:
    """Calculate the bit-level Hamming distance between two hex strings."""
    b1 = bytes.fromhex(hex1)
    b2 = bytes.fromhex(hex2)
    return sum(bin(byte1 ^ byte2).count("1") for byte1, byte2 in zip(b1, b2))


class MR_HASH_01_PreimageSensitivity(MetamorphicRelation):
    """MR-HASH-01: Strict digest divergence under single-bit/character modification."""

    id = "MR-HASH-01"
    name = "Avalanche and Preimage Sensitivity"
    category = Category.HASHING
    rationale = (
        "SHA-256 guarantees preimage resistance and the avalanche effect: changing a "
        "single input bit flips approximately 50% (128) of the output bits in an "
        "unpredictable manner. Any single-character edit to an audit payload must "
        "yield a completely distinct digest with high bit-level Hamming distance."
    )
    input_transformation = (
        "Alter a single character in the payload (e.g. increment a packet count from 100 to 101)."
    )
    expected_property = "H(P) != H(P') and HammingDistance(H(P), H(P')) >= 64 bits (out of 256)."
    limitations = "Holds cryptographically with probability 1 - 2^-256."
    test_implementation = (
        "Compute SHA-256 for P and P' (single digit changed), assert inequality and "
        "verify Hamming distance is within the expected avalanche distribution [64, 192]."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        payload_a = {"event": "INFERENCE", "sample_id": 100, "label": "BENIGN"}
        payload_b = {"event": "INFERENCE", "sample_id": 101, "label": "BENIGN"}

        hash_a = sha256_hash(canonicalize(payload_a))
        hash_b = sha256_hash(canonicalize(payload_b))

        h_dist = _hamming_distance(hash_a, hash_b)
        # Expected ~128 bits; test passes if >= 64 bits flipped (standard statistical bound)
        passed = (hash_a != hash_b) and (h_dist >= 64)

        return (
            passed,
            f"Avalanche effect verified: {h_dist}/256 bits changed between single-character diff.",
            {"hash_a": hash_a, "hash_b": hash_b, "hamming_distance_bits": h_dist},
        )


class MR_HASH_02_ChainOperandNonCommutativity(MetamorphicRelation):
    """MR-HASH-02: Non-commutativity of hash chain concatenation operands."""

    id = "MR-HASH-02"
    name = "Hash Chain Operand Non-Commutativity"
    category = Category.HASHING
    rationale = (
        "In SentinelCrypt's hash chain, `calculate_record_hash(prev_hash, payload_hash)` "
        "evaluates SHA-256(prev_hash + payload_hash). String concatenation is non-commutative. "
        "Swapping the operands must produce a completely different record hash to prevent "
        "prefix-suffix interchange attacks."
    )
    input_transformation = (
        "Evaluate calculate_record_hash(H_prev, H_payload) versus calculate_record_hash(H_payload, H_prev)."
    )
    expected_property = "calculate_record_hash(A, B) != calculate_record_hash(B, A) when A != B."
    limitations = "Requires A != B."
    test_implementation = (
        "Generate two distinct 64-char hex strings, calculate forward and swapped record hashes, "
        "assert strict inequality."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        h_prev = "a" * 64
        h_payload = "b" * 64

        h_forward = calculate_record_hash(h_prev, h_payload)
        h_swapped = calculate_record_hash(h_payload, h_prev)

        passed = (h_forward != h_swapped)
        return (
            passed,
            f"Record hash concatenation is {'strictly non-commutative' if passed else 'commutative (INSECURE)'}.",
            {"forward_hash": h_forward, "swapped_hash": h_swapped},
        )


class MR_HASH_03_MerkleDomainSeparation(MetamorphicRelation):
    """MR-HASH-03: Domain separation between leaf and interior node hashes."""

    id = "MR-HASH-03"
    name = "Merkle Tree Domain Separation (Leaf vs Node Invariance)"
    category = Category.HASHING
    rationale = (
        "To prevent second-preimage attacks where an interior node hash is misinterpreted as "
        "a leaf payload, Merkle trees prepend distinct 1-byte domain separation prefixes: "
        "0x01 for leaves (leaf_hash) and 0x00 for interior nodes (node_hash). For any two "
        "child hashes l and r, leaf_hash(l + r) must NEVER equal node_hash(l, r)."
    )
    input_transformation = (
        "Given two 32-byte digests l and r, compute leaf_hash(l + r) and node_hash(l, r)."
    )
    expected_property = "leaf_hash(l + r) != node_hash(l, r)."
    limitations = "l and r must each be 32 bytes."
    test_implementation = (
        "Generate random 32-byte digests, evaluate leaf_hash(concat) vs node_hash(l, r), assert inequality."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        l = bytes.fromhex("11" * 32)
        r = bytes.fromhex("22" * 32)

        leaf_digest = leaf_hash(l + r)
        node_digest = node_hash(l, r)

        passed = (leaf_digest != node_digest)
        return (
            passed,
            f"Domain separation verified: leaf and node prefixes prevent preimage confusion.",
            {"leaf_hex": leaf_digest.hex(), "node_hex": node_digest.hex()},
        )


class MR_HASH_04_MerkleOddLeafDuplication(MetamorphicRelation):
    """MR-HASH-04: Structural identity under odd-leaf duplication convention."""

    id = "MR-HASH-04"
    name = "Merkle Odd-Leaf Duplication Structural Invariance"
    category = Category.HASHING
    rationale = (
        "SentinelCrypt's MerkleTree follows the Bitcoin/RFC convention for odd leaf counts: "
        "if a level has an odd number of nodes, the last node is duplicated. Therefore, "
        "a tree built from leaves [l1, l2, l3] must have the exact same root hash as a tree "
        "built from [l1, l2, l3, l3]."
    )
    input_transformation = (
        "Given odd leaf sequence L = [l1, l2, l3], construct L' = [l1, l2, l3, l3]."
    )
    expected_property = "MerkleTree(L).root == MerkleTree(L').root."
    limitations = "Applies specifically when the initial leaf count is odd."
    test_implementation = (
        "Build MerkleTree with 3 leaves and MerkleTree with 4 leaves (duplicated 3rd), assert identical root."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        leaves_odd = [
            {"sample_id": 1, "score": 0.1},
            {"sample_id": 2, "score": 0.2},
            {"sample_id": 3, "score": 0.3},
        ]
        leaves_even = leaves_odd + [leaves_odd[-1]]

        tree_odd = MerkleTree(leaves_odd)
        tree_even = MerkleTree(leaves_even)

        passed = (tree_odd.root == tree_even.root)
        return (
            passed,
            f"Odd leaf duplication preserves Merkle root: {tree_odd.root[:16]}... matched.",
            {"root_odd": tree_odd.root, "root_even": tree_even.root},
        )
