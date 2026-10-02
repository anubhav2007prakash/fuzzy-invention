import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.sentinel_verify import canonical_json, main, verify_directory


VERSIONS = {
    "evidence_format_version": 2,
    "protocol_version": 1,
    "schema_version": 1,
    "experiment_schema_version": 1,
    "research_artifact_version": 1,
}


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def _build_package(root):
    run_manifest = {
        "experiment_id": "EXP-CLI",
        "dataset": {"sha256": "a" * 64},
        "random_seed": 7,
    }
    result = {
        "experiment_id": "EXP-CLI",
        "title": "CLI fixture",
        "status": "COMPLETED",
        "metrics": {"f1_macro": 0.75},
        "run_manifest": run_manifest,
        "timestamp": "2026-10-01T12:00:00Z",
    }
    envelope = {
        "run_manifest", "result_hash", "configuration_hash",
        "trust_profile", "evidence_package", "timestamp", "reproducibility",
    }
    result["result_hash"] = hashlib.sha256(
        canonical_json({key: value for key, value in result.items() if key not in envelope})
        .encode("utf-8")
    ).hexdigest()
    _write_json(root / "package-manifest.json", {**VERSIONS, "experiment_id": "EXP-CLI"})
    _write_json(root / "experiment.json", result)
    _write_json(root / "metrics.json", result["metrics"])
    _write_json(root / "reproducibility-manifest.json", run_manifest)
    _write_json(root / "verification-report.json", {
        **VERSIONS,
        "experiment_id": "EXP-CLI",
        "status": result["status"],
        "result_hash": result["result_hash"],
        "configuration_hash": None,
    })
    (root / "README.md").write_text("offline fixture\n", encoding="utf-8")
    inventory = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
    _write_json(root / "file-hashes.json", inventory)
    return result


def _checks(report):
    return {item["check"]: item["status"] for item in report["results"]}


def test_standalone_verifies_direct_evidence_package_and_lineage(tmp_path):
    _build_package(tmp_path)

    report = verify_directory(tmp_path)

    assert report["verified"] is True
    assert report["status"] == "VERIFIED"
    assert _checks(report)["artifact_presence"] == "PASS"
    assert _checks(report)["file_hashes"] == "PASS"
    assert _checks(report)["result_hash"] == "PASS"
    assert _checks(report)["evidence_consistency"] == "PASS"


def test_changed_artifact_fails_hash_and_result_verification(tmp_path):
    _build_package(tmp_path)
    (tmp_path / "metrics.json").write_text('{"f1_macro": 0.99}', encoding="utf-8")

    report = verify_directory(tmp_path)

    assert report["status"] == "FAILED"
    assert report["verified"] is False
    assert _checks(report)["file_hashes"] == "FAIL"
    assert _checks(report)["evidence_consistency"] == "FAIL"


def test_file_hash_inventory_rejects_traversal(tmp_path):
    _build_package(tmp_path)
    _write_json(tmp_path / "file-hashes.json", {"../outside.json": "0" * 64})

    report = verify_directory(tmp_path)

    assert report["status"] == "FAILED"
    assert "Invalid relative path" in next(
        item["detail"] for item in report["results"] if item["check"] == "file_hashes"
    )


def test_unsupported_protocol_version_has_distinct_status_and_exit_code(tmp_path):
    _build_package(tmp_path)
    manifest = json.loads((tmp_path / "package-manifest.json").read_text(encoding="utf-8"))
    manifest["protocol_version"] = 99
    _write_json(tmp_path / "package-manifest.json", manifest)

    report = verify_directory(tmp_path)

    assert report["status"] == "UNSUPPORTED_VERSION"
    assert report["exit_code"] == 3


def test_empty_directory_is_invalid_format_not_verified(tmp_path):
    report = verify_directory(tmp_path)

    assert report["verified"] is False
    assert report["status"] == "INVALID_FORMAT"
    assert report["exit_code"] == 2


def test_malformed_json_is_reported_as_invalid_format(tmp_path):
    _build_package(tmp_path)
    (tmp_path / "experiment.json").write_text("{ broken", encoding="utf-8")

    report = verify_directory(tmp_path)

    assert report["status"] == "INVALID_FORMAT"
    assert report["verified"] is False


def test_duplicate_json_keys_are_rejected_as_invalid_format(tmp_path):
    _build_package(tmp_path)
    (tmp_path / "experiment.json").write_text(
        '{"experiment_id":"EXP-CLI","experiment_id":"EXP-OTHER"}',
        encoding="utf-8",
    )

    report = verify_directory(tmp_path)

    assert report["status"] == "INVALID_FORMAT"
    assert report["verified"] is False
    assert "duplicate JSON object key" in " ".join(
        item["detail"] for item in report["results"]
    )


def test_duplicate_or_reordered_audit_records_fail_chain_check(tmp_path):
    _build_package(tmp_path)
    genesis = "0" * 64
    records = [
        {
            "sequence_number": 1,
            "payload_json": '{"event":"one"}',
            "previous_hash": genesis,
            "record_hash": "1" * 64,
        },
        {
            "sequence_number": 1,
            "payload_json": '{"event":"two"}',
            "previous_hash": "1" * 64,
            "record_hash": "2" * 64,
        },
    ]
    _write_json(tmp_path / "audit-ledger.json", {"protocol_version": 1, "records": records})

    report = verify_directory(tmp_path)

    assert report["status"] == "FAILED"
    assert _checks(report)["audit_chain"] == "FAIL"


def test_reordered_valid_audit_records_fail_chain_check(tmp_path):
    _build_package(tmp_path)
    genesis = "0" * 64
    records = []
    previous = genesis
    for sequence, event in ((1, "one"), (2, "two")):
        payload_json = canonical_json({"event": event})
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        record_hash = hashlib.sha256((previous + payload_hash).encode("utf-8")).hexdigest()
        records.append({
            "sequence_number": sequence,
            "payload_json": payload_json,
            "previous_hash": previous,
            "record_hash": record_hash,
        })
        previous = record_hash
    _write_json(
        tmp_path / "audit-ledger.json",
        {"protocol_version": 1, "records": list(reversed(records))},
    )

    report = verify_directory(tmp_path)

    assert report["status"] == "FAILED"
    assert _checks(report)["audit_chain"] == "FAIL"


def test_deleted_audit_record_is_detected_by_sequence_gap(tmp_path):
    _build_package(tmp_path)
    genesis = "0" * 64
    records = []
    previous = genesis
    for sequence in range(1, 4):
        payload_json = canonical_json({"sequence": sequence})
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        record_hash = hashlib.sha256((previous + payload_hash).encode("utf-8")).hexdigest()
        records.append({
            "sequence_number": sequence,
            "payload_json": payload_json,
            "previous_hash": previous,
            "record_hash": record_hash,
        })
        previous = record_hash
    _write_json(
        tmp_path / "audit-ledger.json",
        {"protocol_version": 1, "records": [records[0], records[2]]},
    )

    report = verify_directory(tmp_path)

    assert report["status"] == "FAILED"
    assert _checks(report)["audit_chain"] == "FAIL"


def test_signature_is_verified_offline_when_present(tmp_path):
    cryptography = pytest.importorskip("cryptography")
    del cryptography
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    _build_package(tmp_path)
    payload = {"experiment_id": "EXP-CLI", "claim": "offline signature"}
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).digest()
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    _write_json(tmp_path / "notary-artifact.json", {
        "artifact_type": "sentinelcrypt.research-artifact.v1",
        "protocol_version": 1,
        "schema_version": 1,
        "research_artifact_version": 1,
        "payload": payload,
        "payload_hash": digest.hex(),
        "signature": base64.b64encode(key.sign(digest)).decode("ascii"),
        "public_key": base64.b64encode(public).decode("ascii"),
    })
    # The package inventory itself is not self-hashed; refresh it to cover the signature.
    inventory = {
        path.relative_to(tmp_path).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file() and path.name != "file-hashes.json"
    }
    _write_json(tmp_path / "file-hashes.json", inventory)

    report = verify_directory(tmp_path)

    assert report["status"] == "VERIFIED"
    assert _checks(report)["notary_signature"] == "PASS"


def test_cli_json_output_uses_exit_code_for_result(tmp_path, capsys):
    _build_package(tmp_path)

    exit_code = main([str(tmp_path), "--json"])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "VERIFIED"


def test_cli_verifies_without_network_application_or_training_runtime(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    _build_package(package)
    verifier = Path(__file__).resolve().parents[3] / "scripts" / "sentinel_verify.py"
    isolated_runner = """
import builtins
import runpy
import socket
import sys

blocked = {"backend", "fastapi", "sqlalchemy", "numpy", "pandas", "sklearn", "shap"}
original_import = builtins.__import__

def deny_application_import(name, *args, **kwargs):
    if name.split(".", 1)[0] in blocked:
        raise AssertionError("offline verifier attempted forbidden import: " + name)
    return original_import(name, *args, **kwargs)

def deny_network(*args, **kwargs):
    raise AssertionError("offline verifier attempted network access")

builtins.__import__ = deny_application_import
socket.socket.connect = deny_network
socket.create_connection = deny_network
sys.argv = [sys.argv[1], sys.argv[2], "--json"]
runpy.run_path(sys.argv[0], run_name="__main__")
"""
    result = subprocess.run(
        [sys.executable, "-S", "-c", isolated_runner, str(verifier), str(package)],
        cwd=tmp_path,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "VERIFIED"
    assert report["exit_code"] == 0
    assert not (package / "dataset.csv").exists()
    assert not (package / "model.pkl").exists()
    assert not (package / "model.onnx").exists()
