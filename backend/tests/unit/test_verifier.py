"""Unit tests for the independent cryptographic verifier and tamper detection algorithms."""
import unittest
from types import SimpleNamespace

from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    build_audit_record_hashes,
    calculate_record_hash,
)
from backend.app.cryptography.hashing import sha256_hash
from backend.app.cryptography.verifier import VerificationResult, verify_ledger


class TestCryptographicVerifier(unittest.TestCase):
    def _create_valid_chain(self, n_records: int = 5):
        records = []
        prev_hash = GENESIS_PREVIOUS_HASH
        for i in range(1, n_records + 1):
            payload = {
                "event_type": "INFERENCE",
                "sample_id": i,
                "score": float(i * 0.1),
                "label": i % 2,
            }
            canon_str, payload_hash, rec_hash = build_audit_record_hashes(payload, prev_hash)
            rec = SimpleNamespace(
                id=f"rec-{i}",
                sequence_number=i,
                payload_json=canon_str,
                previous_hash=prev_hash,
                record_hash=rec_hash,
            )
            records.append(rec)
            prev_hash = rec_hash
        return records

    def test_verify_empty_ledger(self):
        result = verify_ledger([])
        self.assertTrue(result.verified)
        self.assertEqual(result.checked_count, 0)
        self.assertEqual(len(result.failed_records), 0)
        self.assertIn("empty", result.message.lower())

    def test_verify_valid_chain(self):
        chain = self._create_valid_chain(5)
        result = verify_ledger(chain)
        self.assertTrue(result.verified)
        self.assertEqual(result.checked_count, 5)
        self.assertEqual(len(result.failed_records), 0)
        self.assertFalse(result.to_dict()["tamper_detected"])

    def test_detect_payload_tampering(self):
        chain = self._create_valid_chain(5)
        # Adversary mutates payload of record 3 (e.g., changes label 1 to 0)
        tampered_payload = {
            "event_type": "INFERENCE",
            "sample_id": 3,
            "score": 0.3,
            "label": 999,  # tampered value
        }
        chain[2].payload_json = canonicalize(tampered_payload)

        result = verify_ledger(chain)
        self.assertFalse(result.verified)
        self.assertTrue(result.to_dict()["tamper_detected"])
        self.assertGreater(len(result.failed_records), 0)
        # The failure should locate sequence 3
        corrupted_seqs = [f["sequence_number"] for f in result.failed_records]
        self.assertIn(3, corrupted_seqs)

    def test_detect_previous_hash_tampering(self):
        chain = self._create_valid_chain(5)
        # Adversary modifies previous_hash on record 2
        chain[1].previous_hash = "a" * 64

        result = verify_ledger(chain)
        self.assertFalse(result.verified)
        corrupted_seqs = [f["sequence_number"] for f in result.failed_records]
        self.assertIn(2, corrupted_seqs)

    def test_detect_corrupt_record_hash(self):
        chain = self._create_valid_chain(5)
        # Adversary modifies record_hash on record 4
        chain[3].record_hash = "f" * 64

        result = verify_ledger(chain)
        self.assertFalse(result.verified)
        corrupted_seqs = [f["sequence_number"] for f in result.failed_records]
        self.assertIn(4, corrupted_seqs)

    def test_detect_broken_sequence_dropped_record(self):
        chain = self._create_valid_chain(5)
        # Adversary deletes record 3 (chain jumps from 2 to 4)
        del chain[2]

        result = verify_ledger(chain)
        self.assertFalse(result.verified)
        corrupted_types = [f["error_type"] for f in result.failed_records]
        self.assertIn("BROKEN_SEQUENCE", corrupted_types)


if __name__ == "__main__":
    unittest.main()
