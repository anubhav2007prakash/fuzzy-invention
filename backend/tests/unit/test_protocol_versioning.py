import json

import pytest

from backend.app.cryptography.versioning import version_metadata
from scripts.sentinel_verify import verify_directory


def test_current_package_manifest_declares_all_version_dimensions(tmp_path):
    manifest = version_metadata()
    (tmp_path / "package-manifest.json").write_text(json.dumps(manifest))

    report = verify_directory(tmp_path)

    # A manifest alone is not a complete evidence package, even if its versions
    # are supported. Version-specific assertions remain independently useful.
    assert report["status"] == "INVALID_FORMAT"
    assert report["evidence_format_versions_supported"] == ["1", "2"]
    assert report["schema_versions_supported"] == ["1"]
    checks = {item["check"]: item["status"] for item in report["results"]}
    for version_field in manifest:
        assert checks[version_field] == "PASS"


def test_legacy_package_without_manifest_defaults_to_supported_v1(tmp_path):
    report = verify_directory(tmp_path)

    assert report["status"] == "INVALID_FORMAT"
    checks = {item["check"]: item["status"] for item in report["results"]}
    assert checks["evidence_format_version"] == "PASS"
    assert checks["schema_version"] == "PASS"
    assert checks["experiment_schema_version"] == "PASS"


@pytest.mark.parametrize(
    ("field", "unsupported"),
    [
        ("evidence_format_version", 99),
        ("protocol_version", 99),
        ("schema_version", 99),
        ("experiment_schema_version", 99),
        ("research_artifact_version", 99),
    ],
)
def test_package_verifier_rejects_unsupported_versions(tmp_path, field, unsupported):
    manifest = version_metadata()
    manifest[field] = unsupported
    (tmp_path / "package-manifest.json").write_text(json.dumps(manifest))

    report = verify_directory(tmp_path)

    assert report["verified"] is False
    checks = {item["check"]: item["status"] for item in report["results"]}
    assert checks[field] == "FAIL"


def test_manifest_version_one_cannot_claim_the_version_two_layout(tmp_path):
    manifest = dict(version_metadata(), evidence_format_version=1)
    (tmp_path / "package-manifest.json").write_text(json.dumps(manifest))

    report = verify_directory(tmp_path)

    assert report["verified"] is False
    checks = {item["check"]: item["status"] for item in report["results"]}
    assert checks["evidence_format_version"] == "FAIL"


def test_package_verifier_rejects_missing_version_in_explicit_manifest(tmp_path):
    manifest = version_metadata()
    del manifest["schema_version"]
    (tmp_path / "package-manifest.json").write_text(json.dumps(manifest))

    report = verify_directory(tmp_path)

    assert report["verified"] is False
    checks = {item["check"]: item["status"] for item in report["results"]}
    assert checks["schema_version"] == "FAIL"


def test_current_package_requires_versions_in_its_verification_report(tmp_path):
    (tmp_path / "package-manifest.json").write_text(
        json.dumps(version_metadata())
    )
    (tmp_path / "verification-report.json").write_text(
        json.dumps({"experiment_id": "EXP-X"})
    )

    report = verify_directory(tmp_path)

    assert report["verified"] is False
    checks = {item["check"]: item["status"] for item in report["results"]}
    assert checks["protocol_version"] == "FAIL"
    assert checks["schema_version"] == "FAIL"


def test_package_rejects_disagreeing_manifest_and_report_versions(tmp_path):
    manifest = version_metadata()
    report_metadata = dict(manifest, evidence_format_version=1)
    (tmp_path / "package-manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "verification-report.json").write_text(
        json.dumps(report_metadata)
    )

    report = verify_directory(tmp_path)

    assert report["verified"] is False
    checks = {item["check"]: item["status"] for item in report["results"]}
    assert checks["evidence_format_version"] == "FAIL"
