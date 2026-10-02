"""Tests for the Ed25519 research notary."""
import pytest

from backend.app.cryptography import notary


@pytest.fixture(scope="module")
def artifact():
    return notary.sign_result({
        "experiment_id": "EXP-TEST",
        "metrics": {"f1": 0.91},
        "note": "research artifact signing round-trip",
    })


def test_sign_produces_self_contained_artifact(artifact):
    assert artifact["artifact_type"] == "sentinelcrypt.research-artifact.v1"
    assert artifact["protocol_version"] == 1
    assert artifact["schema_version"] == 1
    assert artifact["research_artifact_version"] == 1
    assert artifact["algorithm"] == "Ed25519"
    assert len(artifact["payload_hash"]) == 64
    assert artifact["public_key"]  # verifier needs nothing from the server
    assert artifact["signature"]


def test_verify_round_trip(artifact):
    report = notary.verify_artifact(artifact)
    assert report["valid"] is True
    assert report["signature_valid"] is True
    assert report["digest_match"] is True


def test_legacy_notary_artifact_without_version_fields_remains_verifiable(artifact):
    legacy = {
        key: value
        for key, value in artifact.items()
        if key not in {
            "protocol_version",
            "schema_version",
            "research_artifact_version",
        }
    }

    report = notary.verify_artifact(legacy)

    assert report["valid"] is True
    assert report["signature_valid"] is True


@pytest.mark.parametrize(
    ("field", "version"),
    [
        ("protocol_version", 99),
        ("schema_version", 99),
        ("research_artifact_version", 99),
    ],
)
def test_notary_rejects_unsupported_explicit_versions(artifact, field, version):
    unsupported = dict(artifact, **{field: version})

    report = notary.verify_artifact(unsupported)

    assert report["valid"] is False
    assert field in report["reason"]


def test_notary_rejects_malformed_version_value_without_raising(artifact):
    malformed = dict(artifact, schema_version=[])

    report = notary.verify_artifact(malformed)

    assert report["valid"] is False
    assert "schema_version" in report["reason"]


def test_signed_at_is_not_authenticated_by_payload_signature(artifact):
    altered_envelope = dict(artifact, signed_at="1900-01-01T00:00:00Z")

    report = notary.verify_artifact(altered_envelope)

    assert report["valid"] is True
    assert report["signature_valid"] is True
    assert report["digest_match"] is True
    assert altered_envelope["signed_at"] != artifact["signed_at"]


def test_verify_detects_payload_tampering(artifact):
    tampered = dict(artifact)
    tampered["payload"] = dict(artifact["payload"], metrics={"f1": 0.01})
    report = notary.verify_artifact(tampered)
    assert report["valid"] is False
    assert report["digest_match"] is False


def test_verify_detects_forged_signature_with_foreign_key(artifact):
    import base64
    import hashlib

    from backend.app.cryptography.canonicalization import canonicalize
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    # impostor signs the true digest, but the artifact keeps the ORIGINAL key:
    # the signature check must fail.
    digest = hashlib.sha256(canonicalize(artifact["payload"]).encode("utf-8")).digest()
    impostor = Ed25519PrivateKey.generate()
    forged = dict(artifact)
    forged["signature"] = base64.b64encode(impostor.sign(digest)).decode()
    report = notary.verify_artifact(forged)
    assert report["valid"] is False
    assert report["signature_valid"] is False


def test_self_consistent_foreign_keypair_verifies_but_is_a_different_identity():
    """A fully replaced keypair verifies internally — identity anchoring is the
    fingerprint's job, which is why artifacts carry key_fingerprint."""
    import base64
    import hashlib

    from backend.app.cryptography.canonicalization import canonicalize
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    payload = {"experiment_id": "FORGED", "metrics": {"f1": 0.5}}
    digest = hashlib.sha256(canonicalize(payload).encode("utf-8")).digest()
    attacker = Ed25519PrivateKey.generate()
    artifact = {
        "payload": payload,
        "payload_hash": digest.hex(),
        "signature": base64.b64encode(attacker.sign(digest)).decode(),
        "public_key": base64.b64encode(
            attacker.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).decode(),
    }
    report = notary.verify_artifact(artifact)
    assert report["valid"] is True  # internally consistent
    assert report["key_fingerprint"] != notary.fingerprint()  # ...but not OUR identity


def test_verify_rejects_incomplete_artifact():
    report = notary.verify_artifact({"payload": {"a": 1}})
    assert report["valid"] is False
    assert "missing required fields" in report["reason"]


def test_keypair_is_stable_across_calls():
    assert notary.public_key_b64() == notary.public_key_b64()
    assert len(notary.fingerprint()) == 64
