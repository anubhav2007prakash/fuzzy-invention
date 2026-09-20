"""Unit tests for hashing, canonicalization, and ledger verification."""
import unittest
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hashing import sha256_hash
from backend.app.cryptography.hash_chain import (
    build_audit_record_hashes, GENESIS_PREVIOUS_HASH
)
from backend.app.cryptography.verifier import verify_ledger

class DummyAuditRecord:
    def __init__(self, sequence_number, id, payload_json, previous_hash, record_hash):
        self.sequence_number = sequence_number
        self.id = id
        self.payload_json = payload_json
        self.previous_hash = previous_hash
        self.record_hash = record_hash

class TestCryptographyEngine(unittest.TestCase):
    def test_canonical_json_determinism(self):
        payload_a = {"b": 2, "a": 1, "nested": {"z": 100, "y": 50}}
        payload_b = {"a": 1, "nested": {"y": 50, "z": 100}, "b": 2}
        self.assertEqual(canonicalize(payload_a), canonicalize(payload_b))
        self.assertEqual(sha256_hash(canonicalize(payload_a)), sha256_hash(canonicalize(payload_b)))

    def test_hash_chain_single_record(self):
        payload = {
            "prediction_id": "test-1",
            "predicted_class": "BENIGN",
            "model_version": "rf-v1.0"
        }
        canon, p_hash, r_hash = build_audit_record_hashes(payload, GENESIS_PREVIOUS_HASH)
        self.assertEqual(len(p_hash), 64)
        self.assertEqual(len(r_hash), 64)

        rec = DummyAuditRecord(1, "rec-1", canon, GENESIS_PREVIOUS_HASH, r_hash)
        result = verify_ledger([rec])
        self.assertTrue(result.verified)
        self.assertEqual(result.checked_count, 1)
        self.assertEqual(len(result.failed_records), 0)

    def test_hash_chain_sequential_integrity(self):
        records = []
        prev_hash = GENESIS_PREVIOUS_HASH
        for seq in range(1, 6):
            payload = {"prediction_id": f"pred-{seq}", "class": "BENIGN", "seq": seq}
            canon, _, r_hash = build_audit_record_hashes(payload, prev_hash)
            records.append(DummyAuditRecord(seq, f"rec-{seq}", canon, prev_hash, r_hash))
            prev_hash = r_hash

        result = verify_ledger(records)
        self.assertTrue(result.verified)
        self.assertEqual(result.checked_count, 5)

    def test_tamper_detection_on_modified_payload(self):
        records = []
        prev_hash = GENESIS_PREVIOUS_HASH
        for seq in range(1, 4):
            payload = {"prediction_id": f"pred-{seq}", "class": "BENIGN", "score": 0.1 * seq}
            canon, _, r_hash = build_audit_record_hashes(payload, prev_hash)
            records.append(DummyAuditRecord(seq, f"rec-{seq}", canon, prev_hash, r_hash))
            prev_hash = r_hash

        # Tamper with record 2 payload without updating hash
        records[1].payload_json = '{"class":"ATTACK","prediction_id":"pred-2","score":0.99}'
        result = verify_ledger(records)
        self.assertFalse(result.verified)
        self.assertGreater(len(result.failed_records), 0)
        self.assertEqual(result.failed_records[0]["sequence_number"], 2)

if __name__ == "__main__":
    unittest.main()
