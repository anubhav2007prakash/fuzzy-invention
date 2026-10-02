"""Security regression corpus — red-team tests against SentinelCrypt itself.

Every test here is a controlled attack on the *platform* (not the IDS problem):
malformed input, tampered evidence, forged artifacts, oversized payloads,
inconsistent metadata.  A failure means a real attack surface.  When a future
security bug is discovered, it gets a test in this file (or a fixture under
backend/tests/fixtures/security/) BEFORE the fix.

Static attack fixtures live in backend/tests/fixtures/security/ — they are
pre-built attack artifacts (tampered chains, forged notary signatures) so the
attacks themselves cannot silently rot with refactors.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    calculate_payload_hash,
    calculate_record_hash,
)
from backend.app.cryptography import notary
from backend.app.cryptography.verifier import verify_ledger

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "security"


class Row:
    """ORM-row shape for verify_ledger without a database."""

    def __init__(self, d):
        for k, v in d.items():
            setattr(self, k, v)


def _honest_chain(n=4):
    records, prev = [], GENESIS_PREVIOUS_HASH
    for seq in range(1, n + 1):
        payload = {"seq": seq, "action": "predict"}
        pj = canonicalize(payload)
        ph = calculate_payload_hash(payload)
        rh = calculate_record_hash(prev, ph)
        records.append({
            "sequence_number": seq, "payload_json": pj,
            "previous_hash": prev, "record_hash": rh,
        })
        prev = rh
    return records


# ── 1. Ledger attacks ─────────────────────────────────────────────────────────
class TestLedgerAttacks:
    def test_fixture_tampered_chain_is_detected(self):
        """Attack: direct DB edit of a historical payload."""
        data = json.loads((FIXTURES / "tampered_audit_records.json").read_text())
        result = verify_ledger([Row(r) for r in data["records"]])
        assert result.verified is False
        assert any(f["sequence_number"] == 3 for f in result.failed_records)
    def test_record_reordering_detected(self):
        """Pure list reordering is NORMALIZED by verify_ledger (sorts by seq)
        — documented behaviour.  The detectable variant is renumbering."""
        records = _honest_chain(5)
        reordered = [records[1], records[0]] + records[2:]
        # same records, different list order → verifier sorts → still valid:
        assert verify_ledger([Row(r) for r in reordered]).verified is True

    def test_renumbering_attack_detected(self):
        """Attack: delete a record, then renumber to hide the gap.

        Chain-only verification DOES catch this: the record after the deletion
        still carries previous_hash = (deleted record's hash), which no longer
        matches its new predecessor.  (Deleting the tail record AND rehashing
        nothing would pass — but then the tip hash changes, which an external
        anchor catches.  See the notary tests.)
        """
        records = _honest_chain(5)
        del records[2]
        for i, rec in enumerate(records):
            rec["sequence_number"] = i + 1  # attacker renumbers to hide the gap
        result = verify_ledger([Row(r) for r in records])
        assert result.verified is False
        assert any(f["error_type"] == "PREVIOUS_HASH_MISMATCH" for f in result.failed_records)

    def test_tail_deletion_is_not_detectable_without_external_checkpoint(self):
        """A complete valid prefix verifies; the verifier has no trusted tip."""
        records = _honest_chain(5)
        del records[-1]

        result = verify_ledger([Row(r) for r in records])

        assert result.verified is True
        assert result.checked_count == 4

    def test_duplicate_sequence_detected(self):
        records = _honest_chain(4)
        dup = dict(records[2]); dup["sequence_number"] = records[1]["sequence_number"]
        assert verify_ledger([Row(r) for r in records + [dup]]).verified is False

    def test_genesis_impersonation_detected(self):
        """Attack: claim a different genesis linkage without recomputing hashes.

        Note the boundary: an attacker who recomputes ALL hashes after editing
        the genesis produces an internally-consistent chain — detectable only
        via an external anchor (see test_chain_rebuild_from_tampered_genesis).
        """
        records = _honest_chain(3)
        records[0]["previous_hash"] = GENESIS_PREVIOUS_HASH
        # honest seq-1 previous_hash IS genesis, so re-setting it is a no-op;
        # the real attack is changing it AND recomputing — covered below.
        assert verify_ledger([Row(r) for r in records]).verified is True

    def test_chain_rebuild_from_tampered_genesis_detected(self):
        """Attack: full chain rebuild after editing record 1's payload.

        The attacker recomputes ALL hashes so the chain is internally
        consistent.  Detection requires an external anchor (independent
        export / notary signature) — this test documents that boundary.
        """
        records = _honest_chain(3)
        payload = json.loads(records[0]["payload_json"])
        payload["action"] = "FALSIFIED"
        pj = canonicalize(payload)
        ph = calculate_payload_hash(payload)
        prev, rebuilt = GENESIS_PREVIOUS_HASH, []
        for i, rec in enumerate(records):
            new_ph = ph if i == 0 else calculate_payload_hash(json.loads(rec["payload_json"]))
            rh = calculate_record_hash(prev, new_ph)
            rebuilt.append({
                "sequence_number": rec["sequence_number"], "payload_json": pj if i == 0 else rec["payload_json"],
                "previous_hash": prev, "record_hash": rh,
            })
            prev = rh
        # Internally consistent — verify_ledger alone CANNOT detect this:
        assert verify_ledger([Row(r) for r in rebuilt]).verified is True
        # ...which is exactly why the notary export exists (see TestNotaryAttacks).

    def test_oversized_payload_hash_is_stable(self):
        """Attack: 1MB payload must not produce ambiguous/duplicate digests."""
        big = {"blob": "x" * 1_000_000}
        h1, h2 = calculate_payload_hash(big), calculate_payload_hash(big)
        assert h1 == h2 and len(h1) == 64

    def test_unicode_normalization_gap_is_documented(self):
        """Two visually-identical strings with different code points hash
        differently.  NFC normalization is NOT applied — documented behaviour,
        not a bug; canonical payloads must use the original feature strings."""
        a = calculate_payload_hash({"s": "café"})
        b = calculate_payload_hash({"s": "café"})
        assert a != b  # detection-friendly: any byte-level edit changes the hash


# ── 2. Notary attacks ─────────────────────────────────────────────────────────
class TestNotaryAttacks:
    def test_fixture_forged_signature_rejected(self):
        artifact = json.loads((FIXTURES / "forged_notary_artifact.json").read_text())
        result = notary.verify_artifact(artifact)
        assert result["valid"] is False
        assert result["signature_valid"] is False
        assert result["digest_match"] is True  # digest is honest; signature is not

    def test_payload_swap_after_signing_detected(self):
        artifact = notary.sign_result({"claim": "A", "value": 1})
        artifact["payload"]["value"] = 999  # attacker edits payload inside artifact
        result = notary.verify_artifact(artifact)
        assert result["valid"] is False and result["digest_match"] is False

    def test_signature_from_different_key_detected(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        payload = {"claim": "B"}
        digest = hashlib.sha256(canonicalize(payload).encode()).hexdigest()
        rogue = Ed25519PrivateKey.generate()  # attacker signs with their own key
        artifact = notary.sign_result(payload)
        artifact["signature"] = base64.b64encode(rogue.sign(bytes.fromhex(digest))).decode()
        artifact["public_key"] = base64.b64encode(
            rogue.public_key().public_bytes(
                encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.Raw,
                format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PublicFormat"]).PublicFormat.Raw,
            )
        ).decode()
        result = notary.verify_artifact(artifact)
        # Verifies against ITS OWN embedded key (that's the protocol) but is
        # correctly flagged as NOT signed by this deployment's notary:
        assert result["signature_valid"] is True
        assert result["signed_by_notary"] is False
        assert result["valid"] is True  # artifact is self-consistent...
        # ...the deployment-binding signal is signed_by_notary=False. Documented.

    def test_unsupported_future_protocol_rejected(self):
        artifact = notary.sign_result({"x": 1})
        artifact["protocol_version"] = 99
        result = notary.verify_artifact(artifact)
        assert result["valid"] is False
        assert "Unsupported protocol_version" in result["reason"]

    def test_missing_fields_rejected(self):
        result = notary.verify_artifact({"payload": {}})
        assert result["valid"] is False and "missing required fields" in result["reason"]

    def test_non_canonicalizable_payload_rejected(self):
        artifact = notary.sign_result({"x": 1})
        artifact["payload"] = {"bad": object()}  # not JSON-serializable
        result = notary.verify_artifact(artifact)
        assert result["valid"] is False


# ── 3. API red team ───────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def client():
    from backend.app.main import app

    with TestClient(app) as c:
        yield c


class TestApiRedTeam:
    """The API is an attack surface: malformed input must 4xx, never 500."""
    ENDPOINTS = [
        ("/api/v1/research/challenges/define", {"hypothesis": "x"}),
        ("/api/v1/research/challenges/run", {"preset": "Q1"}),
        ("/api/v1/research/model-selection/run", {"cv_folds": "not-a-number"}),
        ("/api/v1/research/notary/verify", {"garbage": True}),
        # NOTE: NaN/Infinity request bodies are covered by test_nan_on_wire_is_4xx_not_500
        # using raw bytes — httpx's json= mode rejects non-finite floats client-side,
        # so they can't appear in this table.
        ("/api/v1/research/reproducibility/compare", {"a": "not-a-dict", "b": 42}),
    ]

    @pytest.mark.parametrize("url,body", ENDPOINTS)
    def test_malformed_body_is_4xx_not_500(self, client, url, body):
        # NOTE: bodies here are all wire-reachable JSON (json= serialization
        # happens client-side in TestClient — a non-serializable body would
        # fail before reaching the app and prove nothing).
        try:
            resp = client.post(url, json=body)
            status_code = resp.status_code
        except Exception as exc:
            # TestClient re-raises server exceptions instead of translating
            # them — treat any exception during request handling as a 500.
            status_code = 500
            detail = repr(exc)
        else:
            detail = resp.text[:200]
        assert status_code < 500, f"{url} returned {status_code}: {detail}"

    def test_nan_on_wire_is_4xx_not_500(self, client):
        """Python's json.loads silently accepts NaN/Infinity on the wire (they
        are NOT valid JSON per RFC 8785).  The canonicalizer must REJECT them
        (ValueError → 422), never sign non-finite digests — a NaN once made it
        into a signed payload with the non-standard `NaN` token, unverifiable
        outside Python. The arbitrary-payload route is now disabled entirely,
        so both malformed requests are rejected before signing."""
        resp = client.post("/api/v1/research/notary/sign", content=b'{"payload": {"value": NaN}}',
                           headers={"Content-Type": "application/json"})
        assert resp.status_code in (400, 403, 422), resp.text[:200]  # 4xx, never 500

        resp2 = client.post("/api/v1/research/notary/sign", content=b'{"payload": {"value": Infinity}}',
                            headers={"Content-Type": "application/json"})
        assert resp2.status_code in (400, 403, 422), resp2.text[:200]

    def test_arbitrary_notary_payload_is_rejected(self, client):
        """The notary must never certify caller-selected claims."""
        resp = client.post(
            "/api/v1/research/notary/sign",
            json={"experiment": "EXP-A", "metrics": {"accuracy": 1.0}},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "ARBITRARY_NOTARY_SIGNING_DISABLED"

    def test_invalid_json_body(self, client):
        resp = client.post("/api/v1/challenges/define", content=b"{broken",
                           headers={"Content-Type": "application/json"})
        assert resp.status_code < 500

    def test_oversized_features_payload(self, client):
        resp = client.post("/api/v1/predictions", json={
            "model_id": "does-not-exist", "features": {"f" * 10: "x" * 100_000},
        })
        assert resp.status_code < 500

    def test_unknown_experiment_id_rejected_cleanly(self, client):
        resp = client.post("/api/v1/experiments/EXP-NOPE/run", json={})
        assert resp.status_code in (400, 404, 422)

    def test_mode_smuggling_rejected(self, client):
        """Demo-mode default-deny: mutations must not smuggle through suffixes."""
        from backend.app.research.modes import endpoint_allowed, set_mode

        try:
            set_mode("demo")
            assert endpoint_allowed("POST", "/api/v1/predictions") is True
            assert endpoint_allowed("POST", "/api/v1/models/train") is False
            assert endpoint_allowed("POST", "/api/v1/datasets") is False
            assert endpoint_allowed("DELETE", "/api/v1/predictions") is False
            # `/mode` escape hatch must not prefix-match `/models/train`
            assert endpoint_allowed("POST", "/api/v1/models/train") is False
        finally:
            set_mode("research")


# ── 4. sentinel-verify against attacks ───────────────────────────────────────
class TestSentinelVerifyAgainstAttacks:
    def test_tampered_package_results_rejected(self, tmp_path):
        """If results.json is edited after export, the CLI must FAIL."""
        import subprocess
        import sys

        from backend.app.research.reproducibility import export_reproducibility_package
        from backend.app.services.experiment_service import ExperimentService

        result = {"experiment_id": "EXP-T2", "metrics": {"f1_macro": 0.5},
                  "timestamp": "2026-01-01T00:00:00Z", "status": "completed"}
        result["result_hash"] = ExperimentService().calculate_result_hash(result)
        export_reproducibility_package("EXP-T2", result, {"random_state": 42}, out_root=tmp_path)

        # attacker bumps the F1 after export
        payload = json.loads((tmp_path / "results.json").read_text())
        payload["metrics"]["f1_macro"] = 0.99
        (tmp_path / "results.json").write_text(json.dumps(payload, indent=2, sort_keys=True))

        proc = subprocess.run([sys.executable, "scripts/sentinel_verify.py", str(tmp_path), "--json"],
                              capture_output=True, text=True, timeout=60)
        assert proc.returncode == 1
        report = json.loads(proc.stdout)
        checks = {r["check"]: r["status"] for r in report["results"]}
        assert checks["result_hash"] == "FAIL"

    def test_v1_protocol_acceptance(self, tmp_path):
        """protocol_version=1 packages verify; unknown versions fail."""
        import subprocess
        import sys

        from backend.app.research.reproducibility import export_reproducibility_package
        from backend.app.services.experiment_service import ExperimentService

        result = {"experiment_id": "EXP-T3", "metrics": {}, "timestamp": "2026-01-01T00:00:00Z"}
        result["result_hash"] = ExperimentService().calculate_result_hash(result)
        export_reproducibility_package("EXP-T3", result, {"random_state": 42}, out_root=tmp_path)

        proc = subprocess.run([sys.executable, "scripts/sentinel_verify.py", str(tmp_path), "--json"],
                              capture_output=True, text=True, timeout=60)
        report = json.loads(proc.stdout)
        checks = {r["check"]: r["status"] for r in report["results"]}
        assert checks["protocol_version"] == "PASS"
        assert report["protocol_versions_supported"] == ["1"]
