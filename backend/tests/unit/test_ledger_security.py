"""Comprehensive ledger security and tamper detection tests.

Tests at least:
- Normal verification (clean chain)
- Modified payload
- Modified record hash
- Modified previous hash
- Deleted record
- Reordered records
- Duplicate records
- Empty ledger
- Corrupted chain (multiple anomalies)
"""
import json
import unittest
from types import SimpleNamespace

from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    build_audit_record_hashes,
)
from backend.app.cryptography.hashing import sha256_hash
from backend.app.cryptography.verifier import VerificationResult, verify_ledger


class TestLedgerSecurityComprehensive(unittest.TestCase):
    """Comprehensive security tests for the cryptographic audit ledger verifier."""

    def _create_valid_chain(self, n_records: int = 10):
        """Build a valid hash chain of n_records."""
        records = []
        prev_hash = GENESIS_PREVIOUS_HASH
        for i in range(1, n_records + 1):
            payload = {
                "event_type": "INFERENCE",
                "sequence_number": i,
                "timestamp": f"2026-09-21T12:00:{i:02d}Z",
                "model_id": "model-test-01",
                "predicted_class": i % 2,
                "features": {"dur": float(i * 0.1), "rate": float(i * 100)},
            }
            canon_str, p_hash, r_hash = build_audit_record_hashes(payload, prev_hash)
            rec = SimpleNamespace(
                id=f"rec-{i}",
                sequence_number=i,
                payload_json=canon_str,
                previous_hash=prev_hash,
                record_hash=r_hash,
            )
            records.append(rec)
            prev_hash = r_hash
        return records

    # ── 1. Normal verification ────────────────────────────────────────────────

    def test_clean_chain_verified(self):
        """A properly constructed chain should verify successfully."""
        chain = self._create_valid_chain(10)
        result = verify_ledger(chain)
        self.assertTrue(result.verified)
        self.assertEqual(result.checked_count, 10)
        self.assertEqual(len(result.failed_records), 0)

    def test_single_record_chain(self):
        """A single-record chain should verify successfully."""
        chain = self._create_valid_chain(1)
        result = verify_ledger(chain)
        self.assertTrue(result.verified)
        self.assertEqual(result.checked_count, 1)

    def test_large_chain_verified(self):
        """A chain of 100 records should verify successfully."""
        chain = self._create_valid_chain(100)
        result = verify_ledger(chain)
        self.assertTrue(result.verified)
        self.assertEqual(result.checked_count, 100)

    # ── 2. Modified payload ───────────────────────────────────────────────────

    def test_modified_payload_detected(self):
        """Changing a single field in a payload should be detected."""
        chain = self._create_valid_chain(10)
        # Tamper: change predicted_class in record 5
        target_idx = 4
        tampered_payload = json.loads(chain[target_idx].payload_json)
        tampered_payload["predicted_class"] = 999
        chain[target_idx].payload_json = canonicalize(tampered_payload)

        result = verify_ledger(chain)
        self.assertFalse(result.verified)
        self.assertTrue(result.to_dict()["tamper_detected"])
        failed_seqs = [r["sequence_number"] for r in result.failed_records]
        self.assertIn(5, failed_seqs)

    def test_modified_numeric_feature_detected(self):
        """Changing a numeric feature value should be detected."""
        chain = self._create_valid_chain(10)
        target_idx = 3
        tampered_payload = json.loads(chain[target_idx].payload_json)
        tampered_payload["features"]["dur"] = 99999.99
        chain[target_idx].payload_json = canonicalize(tampered_payload)

        result = verify_ledger(chain)
        self.assertFalse(result.verified)
        failed_seqs = [r["sequence_number"] for r in result.failed_records]
        self.assertIn(4, failed_seqs)

    # ── 3. Modified record hash ───────────────────────────────────────────────

    def test_modified_record_hash_detected(self):
        """Changing a record's stored hash should be detected."""
        chain = self._create_valid_chain(10)
        target_idx = 6
        original_hash = chain[target_idx].record_hash
        # Replace with a completely different hash
        chain[target_idx].record_hash = sha256_hash(b"tampered-data")

        result = verify_ledger(chain)
        self.assertFalse(result.verified)
        failed_seqs = [r["sequence_number"] for r in result.failed_records]
        self.assertIn(7, failed_seqs)  # sequence_number is 1-indexed

    def test_record_hash_with_wrong_previous(self):
        """If previous_hash is correct but record_hash is wrong, it should fail."""
        chain = self._create_valid_chain(5)
        # Recompute record hash with wrong previous hash
        chain[2].record_hash = sha256_hash(
            chain[2].previous_hash + sha256_hash(b"wrong")
        )

        result = verify_ledger(chain)
        self.assertFalse(result.verified)

    # ── 4. Modified previous hash ─────────────────────────────────────────────

    def test_modified_previous_hash_detected(self):
        """Changing previous_hash in a record should break the chain."""
        chain = self._create_valid_chain(10)
        target_idx = 5
        chain[target_idx].previous_hash = "a" * 64

        result = verify_ledger(chain)
        self.assertFalse(result.verified)
        failed_seqs = [r["sequence_number"] for r in result.failed_records]
        self.assertIn(6, failed_seqs)

    def test_wrong_genesis_previous_hash(self):
        """Record 1 must have genesis (64 zeros) as previous_hash."""
        chain = self._create_valid_chain(5)
        chain[0].previous_hash = "1" * 64

        result = verify_ledger(chain)
        self.assertFalse(result.verified)
        failed_seqs = [r["sequence_number"] for r in result.failed_records]
        self.assertIn(1, failed_seqs)

    # ── 5. Deleted record ─────────────────────────────────────────────────────

    def test_deleted_record_detected(self):
        """Removing a record from the chain should be detected."""
        chain = self._create_valid_chain(10)
        # Remove record at index 4 (sequence 5)
        del chain[4]

        result = verify_ledger(chain)
        self.assertFalse(result.verified)
        error_types = [r["error_type"] for r in result.failed_records]
        self.assertIn("BROKEN_SEQUENCE", error_types)

    def test_first_record_deleted(self):
        """Removing record 1 should break the genesis link."""
        chain = self._create_valid_chain(5)
        del chain[0]  # Remove sequence 1

        result = verify_ledger(chain)
        self.assertFalse(result.verified)

    # ── 6. Reordered records ──────────────────────────────────────────────────

    def test_reordered_records_still_verify(self):
        """Swapping two records in the input list should NOT break verification.

        The verifier sorts records by sequence_number internally, so receiving
        records in a different order is not a tamper scenario. The important
        thing is that the hash chain itself is intact.
        """
        chain = self._create_valid_chain(10)
        # Swap records 3 and 4 (same records, just different list order)
        chain[2], chain[3] = chain[3], chain[2]

        result = verify_ledger(chain)
        # Should verify because verifier sorts by sequence_number
        self.assertTrue(result.verified)

    def test_out_of_order_detection(self):
        """Records provided out of order should still be checked (sorted by seq)."""
        chain = self._create_valid_chain(5)
        # Reverse the order
        chain.reverse()

        result = verify_ledger(chain)
        # Should verify because verifier sorts by sequence_number
        self.assertTrue(result.verified)
        self.assertEqual(result.checked_count, 5)

    # ── 7. Duplicate records ──────────────────────────────────────────────────

    def test_duplicate_sequence_numbers_detected(self):
        """Two records with the same sequence number should be detected."""
        chain = self._create_valid_chain(5)
        # Duplicate record 3 (append a copy)
        duplicate = SimpleNamespace(
            id="dup-3",
            sequence_number=3,  # Same as existing record 3
            payload_json=chain[2].payload_json,
            previous_hash=chain[2].previous_hash,
            record_hash=chain[2].record_hash,
        )
        chain.append(duplicate)

        result = verify_ledger(chain)
        # The verifier sorts by sequence and checks order
        # With duplicates, it should detect broken sequence
        self.assertFalse(result.verified)

    # ── 8. Empty ledger ───────────────────────────────────────────────────────

    def test_empty_ledger_verified(self):
        """An empty ledger should verify successfully (nothing to check)."""
        result = verify_ledger([])
        self.assertTrue(result.verified)
        self.assertEqual(result.checked_count, 0)
        self.assertEqual(len(result.failed_records), 0)
        self.assertIn("empty", result.message.lower())

    # ── 9. Corrupted chain (multiple anomalies) ──────────────────────────────

    def test_corrupted_chain_multiple_failures(self):
        """A chain with multiple corruptions should report all failures."""
        chain = self._create_valid_chain(10)
        # Tamper record 2: modify payload
        tampered = json.loads(chain[1].payload_json)
        tampered["predicted_class"] = 999
        chain[1].payload_json = canonicalize(tampered)
        # Tamper record 6: modify previous_hash
        chain[5].previous_hash = "ff" * 32
        # Delete record 8
        chain = [r for r in chain if r.sequence_number != 8]

        result = verify_ledger(chain)
        self.assertFalse(result.verified)
        self.assertGreaterEqual(len(result.failed_records), 2)
        # Should have failures at sequences 2, 6, and 8+ area
        failed_seqs = [r["sequence_number"] for r in result.failed_records]
        self.assertIn(2, failed_seqs)

    # ── 10. Verification timing ───────────────────────────────────────────────

    def test_verification_completes_in_reasonable_time(self):
        """Verification of 100 records should complete within 1 second."""
        import time
        chain = self._create_valid_chain(100)
        start = time.perf_counter()
        result = verify_ledger(chain)
        elapsed = time.perf_counter() - start
        self.assertTrue(result.verified)
        self.assertLess(elapsed, 1.0)

    # ── 11. VerificationResult.to_dict() completeness ─────────────────────────

    def test_verification_result_dict_keys(self):
        """to_dict() should contain all required fields."""
        chain = self._create_valid_chain(5)
        result = verify_ledger(chain)
        d = result.to_dict()
        required_keys = [
            "verified", "checked_records", "failed_records",
            "tamper_detected", "verification_duration_ms", "message",
        ]
        for key in required_keys:
            self.assertIn(key, d)

    def test_failed_records_contain_error_type(self):
        """Each failed record should have an error_type field."""
        chain = self._create_valid_chain(5)
        chain[2].payload_json = canonicalize({"tampered": True})
        result = verify_ledger(chain)
        for rec in result.failed_records:
            self.assertIn("error_type", rec)


if __name__ == "__main__":
    unittest.main()
