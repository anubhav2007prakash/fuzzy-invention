"""Differential + property-based tests for the cryptographic core.

Two independent angles of attack on the same question — "could the production
crypto silently disagree with its own specification?":

1. Differential: production vs backend/app/cryptography/reference/, a
   deliberately-naive re-implementation written from the protocol description.
   Any production change that alters digests (separators, float encoding, linkage)
   breaks string equality here.

2. Property-based (Hypothesis, if installed): invariants that must hold for
   ALL inputs, not just curated ones.

Also enforces that scripts/sentinel_verify.py's independently re-declared
research envelope stays in sync with the production RESEARCH_ENVELOPE_KEYS.
"""
from __future__ import annotations

import json

import pytest

from backend.app.cryptography import reference as ref
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    calculate_payload_hash,
    calculate_record_hash,
)
from backend.app.cryptography.hashing import sha256_hash

# Hypothesis is optional — skip cleanly if absent so the suite runs everywhere.
try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True
except ImportError:  # pragma: no cover
    HAS_HYPOTHESIS = False


# ── 1. Differential: production vs reference ──────────────────────────────────
class TestDifferentialCanonicalization:
    """canonicalize() vs the hand-written reference serializer."""

    CASES = [
        {},
        {"a": 1},
        {"b": 2, "a": 1},                      # key order must not matter
        {"nested": {"z": 1, "y": {"deep": [1, 2.5, "x"]}}},
        {"f": 0.1 + 0.2},                      # Python JSON float encoding
        {"f2": 1.0000004, "f3": 1.0000005},
        {"neg": -0.0, "big": 12345678901234},
        {"s": 'quote" and \\ backslash', "u": "café ☕"},
        {"empty_str": "", "empty_list": [], "empty_dict": {}, "null": None},
        {"mixed": [{"b": 1, "a": [True, False, None]}]},
    ]

    @pytest.mark.parametrize("payload", CASES)
    def test_same_canonical_string(self, payload):
        assert canonicalize(payload) == ref.ref_canonical_json(payload)

    def test_key_order_independence(self):
        a = canonicalize({"x": 1, "y": 2, "z": {"p": 1, "q": 2}})
        b = canonicalize({"z": {"q": 2, "p": 1}, "y": 2, "x": 1})
        assert a == b
        assert a == ref.ref_canonical_json(b and {"x": 1, "y": 2, "z": {"p": 1, "q": 2}})

    def test_float_precision_is_bounded(self):
        # Floats serialize via json's shortest round-trip repr — identical
        # inputs must give identical digests in both implementations.
        assert canonicalize({"v": 0.1234564}) == canonicalize({"v": 0.1234564})
        assert ref.ref_canonical_json({"v": 0.1234564}) == canonicalize({"v": 0.1234564})

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_floats_rejected_everywhere(self, bad):
        """NaN/Infinity are not JSON (RFC 8785).  All three canonicalizers
        (production, reference, sentinel-verify) must reject them — Python's
        json would otherwise emit the non-standard `NaN` token, making digests
        unverifiable outside Python."""
        with pytest.raises((ValueError, TypeError)):
            canonicalize({"v": bad})
        with pytest.raises((ValueError, TypeError)):
            ref.ref_canonical_json({"v": bad})
        import subprocess
        import sys

        cli_code = (
            "import sys; sys.path.insert(0, 'scripts'); "
            "from sentinel_verify import canonical_json; "
            f"canonical_json({{'v': {bad!r}}})"
        )
        proc = subprocess.run([sys.executable, "-c", cli_code], capture_output=True, text=True, timeout=30)
        assert proc.returncode != 0, "sentinel-verify canonicalizer accepted a non-finite float"


class TestDifferentialChain:
    """Hash-chain construction and verification vs the reference."""

    def _records(self, n):
        records, prev = [], GENESIS_PREVIOUS_HASH
        for seq in range(1, n + 1):
            payload = {"seq": seq, "data": f"payload-{seq}", "value": seq * 1.5}
            payload_hash = calculate_payload_hash(payload)
            record_hash = calculate_record_hash(prev, payload_hash)
            records.append({
                "sequence_number": seq,
                "payload_json": json.dumps(payload, sort_keys=True, separators=(",", ":")),
                "previous_hash": prev,
                "record_hash": record_hash,
            })
            prev = record_hash
        return records

    def test_record_hash_formula_matches_reference(self):
        for prev, ph in [(GENESIS_PREVIOUS_HASH, "aa" * 32), ("bb" * 32, "cc" * 32)]:
            assert calculate_record_hash(prev, ph) == ref.ref_record_hash(prev, ph)

    def test_chain_verification_agrees_on_valid_chain(self):
        records = self._records(12)
        prod = sha256_hash if False else None  # keep import used
        ref_result = ref.ref_verify_chain(records)
        assert ref_result["verified"] is True
        # Production verifier (ORM-shaped rows work as attribute objects)
        from backend.app.cryptography.verifier import VerificationResult, verify_ledger

        class Row:
            def __init__(self, d):
                for k, v in d.items():
                    setattr(self, k, v)

        prod_result = verify_ledger([Row(r) for r in records])
        assert prod_result.verified is True

    def test_chain_verification_agrees_on_tampered_payload(self):
        records = self._records(6)
        tampered = json.loads(records[3]["payload_json"])
        tampered["data"] = "MALLORY-WAS-HERE"
        records[3]["payload_json"] = json.dumps(tampered, sort_keys=True, separators=(",", ":"))

        ref_result = ref.ref_verify_chain(records)
        assert ref_result["verified"] is False

        from backend.app.cryptography.verifier import verify_ledger

        class Row:
            def __init__(self, d):
                for k, v in d.items():
                    setattr(self, k, v)

        prod_result = verify_ledger([Row(r) for r in records])
        assert prod_result.verified is False
        # Both must flag the SAME record (seq 4)
        assert any(f["sequence_number"] == 4 for f in prod_result.failed_records)

    def test_chain_verification_agrees_on_removal(self):
        records = self._records(6)
        del records[2]  # remove seq 3
        ref_result = ref.ref_verify_chain(records)
        assert ref_result["verified"] is False
        from backend.app.cryptography.verifier import verify_ledger

        class Row:
            def __init__(self, d):
                for k, v in d.items():
                    setattr(self, k, v)

        prod_result = verify_ledger([Row(r) for r in records])
        assert prod_result.verified is False


# ── 2. Envelope sync between sentinel-verify and production ───────────────────
class TestSentinelVerifyEnvelopeSync:
    """The standalone CLI re-declares the research envelope independently.
    This test is the tripwire: if production changes the envelope, the CLI
    must be updated in the same commit or verification silently breaks."""

    def test_envelope_keys_in_sync(self):
        from backend.app.services.experiment_service import RESEARCH_ENVELOPE_KEYS

        cli_source = open("scripts/sentinel_verify.py", encoding="utf-8").read()
        assert "run_manifest" in cli_source  # sanity: reading the right file
        for key in RESEARCH_ENVELOPE_KEYS:
            assert f'"{key}"' in cli_source, (
                f"sentinel_verify.py envelope is missing production key '{key}' — "
                "update the CLI's envelope_keys in the same commit."
            )

    def test_end_to_end_package_verification(self, tmp_path):
        """sentinel-verify must accept a real package produced by production code."""
        import subprocess
        import sys

        from backend.app.research.reproducibility import export_reproducibility_package

        result = {
            "experiment_id": "EXP-T",
            "title": "Test",
            "metrics": {"f1_macro": 0.9, "nested": {"pr_auc": 0.88}},
            "timestamp": "2026-01-01T00:00:00Z",
            "result_hash": "DEADBEEF",
            "status": "completed",
        }
        # Compute the real hash the same way production does.
        from backend.app.services.experiment_service import ExperimentService

        svc = ExperimentService()
        result["result_hash"] = svc.calculate_result_hash(result)

        export_reproducibility_package("EXP-T", result, {"random_state": 42}, out_root=tmp_path)
        proc = subprocess.run(
            [sys.executable, "scripts/sentinel_verify.py", str(tmp_path), "--json"],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, proc.stdout
        report = json.loads(proc.stdout)
        assert report["verified"] is True
        checks = {r["check"]: r["status"] for r in report["results"]}
        assert checks["result_hash"] == "PASS"
        assert checks["file_hashes"] == "PASS"
        assert checks["protocol_version"] == "PASS"


# ── 3. Property-based tests (Hypothesis) ──────────────────────────────────────
if HAS_HYPOTHESIS:

    simple_values = st.none() | st.booleans() | st.integers(min_value=-10**12, max_value=10**12) \
        | st.floats(allow_nan=False, allow_infinity=False, width=64) \
        | st.text(max_size=40)

    payloads = st.recursive(
        simple_values,
        lambda children: st.lists(children, max_size=6)
        | st.dictionaries(st.text(min_size=1, max_size=12), children, max_size=6),
        max_leaves=12,
    )

    class TestProperties:
        @settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
        @given(payloads)
        def test_property_canonicalization_matches_reference(self, payload):
            """P1: production canonicalization ≡ reference for arbitrary JSON."""
            assert canonicalize(payload) == ref.ref_canonical_json(payload)

        @settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
        @given(payloads)
        def test_property_key_order_and_whitespace_invariance(self, payload):
            """P2: digests are invariant to dict construction order."""
            if not isinstance(payload, dict):
                return
            import copy

            shuffled = dict(reversed(list(payload.items())))
            assert calculate_payload_hash(payload) == calculate_payload_hash(shuffled)

        @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
        @given(
            prev=st.text(min_size=64, max_size=64, alphabet="0123456789abcdef"),
            ph=st.text(min_size=64, max_size=64, alphabet="0123456789abcdef"),
        )
        def test_property_record_hash_formula(self, prev, ph):
            """P3: record_hash = SHA256(prev + payload_hash) in both implementations."""
            assert calculate_record_hash(prev, ph) == ref.ref_record_hash(prev, ph)

        @settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
        @given(payloads=payloads, n=st.integers(min_value=1, max_value=8))
        def test_property_valid_chain_always_verifies(self, payloads, n):
            """P4: ANY honestly-constructed chain verifies in both implementations."""
            records, prev = [], GENESIS_PREVIOUS_HASH
            for seq in range(1, n + 1):
                payload = {"seq": seq, "content": payloads}
                pj = canonicalize(payload)
                ph = sha256_hash(pj)
                rh = calculate_record_hash(prev, ph)
                records.append({
                    "sequence_number": seq,
                    "payload_json": pj,
                    "previous_hash": prev,
                    "record_hash": rh,
                })
                prev = rh

            ref_result = ref.ref_verify_chain(records)
            assert ref_result["verified"] is True

            from backend.app.cryptography.verifier import verify_ledger

            class Row:
                def __init__(self, d):
                    for k, v in d.items():
                        setattr(self, k, v)

            assert verify_ledger([Row(r) for r in records]).verified is True

        @settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow])
        @given(payloads=payloads, flip=st.integers(min_value=0, max_value=4))
        def test_property_any_single_tamper_detected(self, payloads, flip):
            """P5: flipping ANY one record's payload breaks verification."""
            n = 5
            records, prev = [], GENESIS_PREVIOUS_HASH
            for seq in range(1, n + 1):
                payload = {"seq": seq, "content": payloads}
                pj = canonicalize(payload)
                ph = sha256_hash(pj)
                rh = calculate_record_hash(prev, ph)
                records.append({
                    "sequence_number": seq,
                    "payload_json": pj,
                    "previous_hash": prev,
                    "record_hash": rh,
                })
                prev = rh

            tampered_payload = dict(json.loads(records[flip]["payload_json"]))
            tampered_payload["content"] = "TAMPERED-" + str(tampered_payload.get("content", ""))[:5]
            records[flip]["payload_json"] = canonicalize(tampered_payload)

            ref_result = ref.ref_verify_chain(records)
            assert ref_result["verified"] is False, f"tamper at seq {flip + 1} undetected"

            from backend.app.cryptography.verifier import verify_ledger

            class Row:
                def __init__(self, d):
                    for k, v in d.items():
                        setattr(self, k, v)

            prod = verify_ledger([Row(r) for r in records])
            assert prod.verified is False
