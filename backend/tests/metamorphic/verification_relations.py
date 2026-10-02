"""Metamorphic Relations for Audit Ledger Verification and Notary Proofs."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    build_audit_record_hashes,
)
from backend.app.cryptography.notary import sign_result, verify_artifact
from backend.app.cryptography.verifier import verify_ledger
from backend.tests.metamorphic.fixtures import DummyAuditRecord, create_honest_chain
from backend.tests.metamorphic.framework import (
    Category,
    MetamorphicRelation,
)


class MR_VER_01_InductiveExtensionInvariance(MetamorphicRelation):
    """MR-VER-01: Inductive preservation of validity upon appending valid records."""

    id = "MR-VER-01"
    name = "Inductive Chain Extension Invariance"
    category = Category.VERIFICATION
    rationale = (
        "A forward-linked cryptographic hash chain is an append-only inductive log. "
        "If a ledger of length k is authentic and verifies against genesis, appending a "
        "newly constructed valid record k+1 (whose previous_hash links to record k's "
        "record_hash) must preserve validity across all k+1 records without altering "
        "historical verification status."
    )
    input_transformation = (
        "Given authentic ledger L of length k, append a newly minted honest record R_{k+1}."
    )
    expected_property = (
        "verify_ledger(L).verified == True implies verify_ledger(L + [R_{k+1}]).verified == True "
        "and checked_count == k + 1."
    )
    limitations = "The appended record must be honestly constructed according to chain protocol."
    test_implementation = (
        "Create authentic chain of 4 records, verify it passes. Append a 5th valid record, "
        "verify the extended chain passes and checked_count increases by 1."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        chain = create_honest_chain(n_records=4)
        res_initial = verify_ledger(chain)
        if not res_initial.verified:
            return False, "Initial 4-record chain failed verification.", {}

        # Append 5th record
        prev_hash = chain[-1].record_hash
        payload_5 = {
            "event_type": "INFERENCE",
            "prediction_id": "pred-uuid-5",
            "model_version": "v1.0.0",
            "features": {"f1": 6.0, "f2": 0.5},
            "predicted_class": "BENIGN",
            "sequence": 5,
        }
        canon, _, r_hash = build_audit_record_hashes(payload_5, prev_hash)
        rec_5 = DummyAuditRecord(5, "rec-5", canon, prev_hash, r_hash)
        extended_chain = chain + [rec_5]

        res_extended = verify_ledger(extended_chain)
        passed = res_extended.verified and (res_extended.checked_count == 5)

        return (
            passed,
            f"Inductive extension {'verified successfully' if passed else 'failed'}.",
            {"initial_count": 4, "extended_count": res_extended.checked_count},
        )


class MR_VER_02_SingleRecordTamperSensitivity(MetamorphicRelation):
    """MR-VER-02: Sensitivity to single-record payload corruption."""

    id = "MR-VER-02"
    name = "Monotonic Tamper Sensitivity (Single Record Corruption)"
    category = Category.VERIFICATION
    rationale = (
        "The core guarantee of SentinelCrypt's evidence ledger is tamper detection. "
        "Mutating any record's stored payload string (e.g. flipping class prediction "
        "from BENIGN to ATTACK) without updating its hash must cause `verify_ledger` "
        "to fail and pinpoint the compromised record sequence number."
    )
    input_transformation = (
        "In an authentic chain L, modify the payload_json of record i (e.g. i=2)."
    )
    expected_property = (
        "verify_ledger(L').verified == False, tamper_detected == True, "
        "and failed_records flags sequence number i."
    )
    limitations = "Assumes attacker does not forge a complete valid chain from genesis."
    test_implementation = (
        "Take authentic 4-record chain, mutate payload of record 2, verify verification fails."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        chain = create_honest_chain(n_records=4)

        # Tamper record 2 payload by mutating a field
        import json
        payload_obj = json.loads(chain[1].payload_json)
        payload_obj["predicted_class"] = "TAMPERED_CLASS_MUTATION"
        chain[1].payload_json = json.dumps(payload_obj)

        res = verify_ledger(chain)
        failed_seqs = [f.get("sequence_number") for f in res.failed_records]
        passed = (not res.verified) and (2 in failed_seqs)

        return (
            passed,
            f"Tamper detection {'successfully flagged record 2' if passed else 'failed to catch mutation'}.",
            {"tamper_detected": not res.verified, "flagged_sequences": failed_seqs},
        )


class MR_VER_03_PrefixValidityUnderTruncation(MetamorphicRelation):
    """MR-VER-03: Preservation of validity for historical prefix chains."""

    id = "MR-VER-03"
    name = "Prefix Validity Under Truncation"
    category = Category.VERIFICATION
    rationale = (
        "Any historical prefix of an authentic forward-linked ledger starting at genesis "
        "(L_{1..m} for 1 <= m < k) is mathematically a complete and valid audit ledger. "
        "Verification must succeed for any initial checkpoint."
    )
    input_transformation = (
        "Given authentic ledger of length k=5, construct truncated prefixes of length 1, 2, 3, 4."
    )
    expected_property = "For all m in [1..k], verify_ledger(L_{1..m}).verified == True."
    limitations = "The sub-chain must be a prefix starting from sequence 1."
    test_implementation = (
        "Construct 5-record chain, slice prefixes of length 1 through 4, verify all succeed."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        chain = create_honest_chain(n_records=5)

        prefix_results = []
        for m in range(1, 5):
            res = verify_ledger(chain[:m])
            prefix_results.append((m, res.verified, res.checked_count))

        all_passed = all(verified and count == m for m, verified, count in prefix_results)
        return (
            all_passed,
            f"All {len(prefix_results)} prefixes {'verified validly' if all_passed else 'failed'}.",
            {"prefix_checks": [{"length": m, "verified": v} for m, v, _ in prefix_results]},
        )


class MR_VER_04_NonGenesisSuffixRejection(MetamorphicRelation):
    """MR-VER-04: Rejection of non-genesis truncated suffixes."""

    id = "MR-VER-04"
    name = "Non-Genesis Suffix Rejection (Genesis Anchor Invariance)"
    category = Category.VERIFICATION
    rationale = (
        "The audit ledger requires that sequence number 1 links to GENESIS_PREVIOUS_HASH. "
        "An adversary cannot take an arbitrary middle section of an authentic ledger "
        "(e.g. records 2..4) and claim it is a complete valid audit trail. Verification "
        "must reject such suffixes due to sequence or genesis pointer mismatch."
    )
    input_transformation = (
        "Drop record 1 from authentic ledger L to evaluate suffix L_{2..k}."
    )
    expected_property = "verify_ledger(L_{2..k}).verified == False."
    limitations = "Requires authentic chain length k >= 2."
    test_implementation = (
        "Pass suffix chain[1:] (records 2..4) to verify_ledger, assert verification fails."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        chain = create_honest_chain(n_records=4)
        suffix_chain = chain[1:]  # records 2, 3, 4

        res = verify_ledger(suffix_chain)
        passed = (not res.verified) and (len(res.failed_records) > 0)

        return (
            passed,
            f"Non-genesis suffix was {'correctly rejected' if passed else 'erroneously accepted'}.",
            {"verified": res.verified, "message": res.message},
        )


class MR_VER_05_NotaryPayloadDigestEntanglement(MetamorphicRelation):
    """MR-VER-05: Entanglement of signed payload and recorded digest."""

    id = "MR-VER-05"
    name = "Notary Artifact Payload-Digest Entanglement"
    category = Category.VERIFICATION
    rationale = (
        "In SentinelCrypt's research notary service, an artifact contains an Ed25519 signature "
        "over the SHA-256 digest of canonicalized payload. Modifying any field in the payload "
        "without re-signing breaks digest matching and signature verification."
    )
    input_transformation = (
        "Sign honest payload P with sign_result to produce artifact A. Modify a value in A['payload']."
    )
    expected_property = "verify_artifact(A').valid == False and digest_match == False."
    limitations = "Private key is not available to the adversary to sign the altered payload."
    test_implementation = (
        "Call sign_result on experiment dict, alter a metric value in payload, call verify_artifact, "
        "assert valid is False and digest_match is False."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        payload = {
            "experiment": "EXP-A-baseline",
            "accuracy": 0.9842,
            "f1_score": 0.9810,
            "model": "random_forest_v1",
        }

        artifact = sign_result(payload)
        # Verify clean artifact passes
        initial_check = verify_artifact(artifact)
        if not initial_check.get("valid"):
            return False, "Initial notary artifact failed verification.", {}

        # Follow-up: tamper with accuracy
        tampered_artifact = dict(artifact)
        tampered_artifact["payload"] = dict(payload)
        tampered_artifact["payload"]["accuracy"] = 0.9999  # inflated metric

        tampered_check = verify_artifact(tampered_artifact)
        passed = (not tampered_check.get("valid")) and (not tampered_check.get("digest_match"))

        return (
            passed,
            f"Notary payload tampering was {'detected and rejected' if passed else 'missed'}.",
            {
                "tampered_valid": tampered_check.get("valid"),
                "digest_match": tampered_check.get("digest_match"),
                "reason": tampered_check.get("reason"),
            },
        )
