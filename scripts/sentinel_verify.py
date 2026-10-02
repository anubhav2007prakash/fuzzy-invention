#!/usr/bin/env python3
"""sentinel-verify — independent, offline verification of SentinelCrypt evidence.

Design constraints (Devil's-Advocate phase, item 18/19/20):
  * Standard-library base operation; optional cryptography import only when a
    signed artifact is present. No app imports at all.
      -> the verifier cannot inherit an application bug from the code it checks.
  * No database, no server, no internet.  Point it at a directory and it
    verifies hashes, chain linkage, notary signatures, and manifest integrity.

Usage:
    python scripts/sentinel_verify.py <evidence-package-dir> [--json]

Exit codes: 0 = VERIFIED, 1 = FAILED, 2 = INVALID_FORMAT / usage error,
            3 = UNSUPPORTED_VERSION.

What it verifies (when present in the package):
  verification-report.json   schema + declared result_hash recomputation
  results.json / evidence/experiment.json   canonical digest recomputation
  file hashes + package_hash  (file-hashes.json if exported)
  audit-ledger.json           SHA-256 forward chain (sentinelcrypt.audit-ledger.v1)
  notary-artifact.json        Ed25519 signature over the canonical payload

Supported protocol versions: sentinelcrypt.*.v1 (see PROTOCOL_VERSIONS).
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── protocol versioning ───────────────────────────────────────────────────────
PROTOCOL_VERSIONS: Dict[str, Dict[str, str]] = {
    "1": {
        "artifact_type": "sentinelcrypt.research-artifact.v1",
        "audit_type": "sentinelcrypt.audit-ledger.v1",
        "note": "Initial protocol: canonical JSON + SHA-256 chain + Ed25519 notary.",
    },
}
SUPPORTED_PROTOCOL_VERSIONS = sorted(PROTOCOL_VERSIONS)
SUPPORTED_EVIDENCE_FORMAT_VERSIONS = ["1", "2"]
SUPPORTED_SCHEMA_VERSIONS = ["1"]
SUPPORTED_EXPERIMENT_SCHEMA_VERSIONS = ["1"]
SUPPORTED_RESEARCH_ARTIFACT_VERSIONS = ["1"]


def _err(check: str, msg: str) -> Dict[str, str]:
    return {"check": check, "status": "FAIL", "detail": msg}


def _ok(check: str, msg: str) -> Dict[str, str]:
    return {"check": check, "status": "PASS", "detail": msg}


def _warn(check: str, msg: str) -> Dict[str, str]:
    return {"check": check, "status": "WARN", "detail": msg}


# ── canonicalization (independent re-implementation, mirrors the protocol doc) ─
def canonical_json(value: Any) -> str:
    """Canonical JSON: sorted keys, no whitespace, shortest-round-trip floats,
    ISO datetimes.  Non-finite floats (NaN/Infinity) are rejected: they are
    not valid JSON and would make digests unverifiable outside Python.

    Deliberately re-implemented here rather than imported: if the production
    serializer ever diverges, this file is the independent cross-check.
    """
    import datetime as _dt
    import math as _math

    if value is None or isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not _math.isfinite(value):
            raise ValueError(f"non-finite float {value!r} is not JSON")
        return json.dumps(value)
    if isinstance(value, (_dt.datetime,)):
        if value.tzinfo is None:
            value = value.replace(tzinfo=_dt.timezone.utc)
        return json.dumps(value.isoformat(), ensure_ascii=False)
    if isinstance(value, dict):
        items = sorted((str(k), v) for k, v in value.items())
        return "{" + ",".join(
            json.dumps(k, ensure_ascii=False) + ":" + canonical_json(v)
            for k, v in items
        ) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonical_json(v) for v in value) + "]"
    raise TypeError(f"unsupported type {type(value).__name__}")


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _unique_json_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    """Reject duplicate keys so parsers cannot disagree about signed content."""
    value: Dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        value[key] = item
    return value


def _loads_json(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_unique_json_object)


def _read_json(path: Path) -> Any:
    """Read UTF-8 JSON, rejecting duplicate keys and preserving diagnostics."""
    try:
        return _loads_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"Cannot read {path.name} as UTF-8 JSON: {exc}") from exc


def _safe_package_file(root: Path, relative: str) -> Optional[Path]:
    """Resolve a package path while preventing traversal and symlink escapes."""
    if not isinstance(relative, str) or not relative or "\x00" in relative:
        return None
    candidate = Path(relative)
    if (
        candidate.is_absolute()
        or "\\" in relative
        or any(part in ("..", "") for part in candidate.parts)
    ):
        return None
    try:
        resolved_root = root.resolve(strict=True)
        resolved = (resolved_root / candidate).resolve(strict=False)
        resolved.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError):
        return None
    return resolved


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def check_package_structure(root: Path, results: List[Dict[str, str]]) -> None:
    """Validate the supported package layouts and minimum artifact schemas."""
    has_manifest = (root / "package-manifest.json").is_file()
    if has_manifest:
        required = (
            "package-manifest.json",
            "verification-report.json",
        )
        missing = [name for name in required if not (root / name).is_file()]
        if missing:
            results.append(_err(
                "package_structure",
                f"Format-2 package is missing required files: {', '.join(missing)}.",
            ))
            return

    direct = (root / "experiment.json").is_file()
    reproducibility = (root / "results.json").is_file()
    if not direct and not reproducibility:
        results.append(_err(
            "package_structure",
            "No supported evidence payload found (expected experiment.json or results.json).",
        ))
        return

    expected = (
        (
            "experiment.json", "metrics.json", "reproducibility-manifest.json",
            *(("file-hashes.json",) if has_manifest else ()),
        )
        if direct
        else (
            "results.json",
            "metrics.csv",
            "model-metadata.json",
            "dataset-manifest.json",
            "environment.json",
            "file-hashes.json",
            "evidence/experiment.json",
        )
    )
    missing = [name for name in expected if not (root / name).is_file()]
    if missing:
        results.append(_err(
            "artifact_presence",
            f"Evidence package is missing required artifacts: {', '.join(missing)}.",
        ))
    else:
        results.append(_ok(
            "artifact_presence",
            f"Required {'experiment evidence' if direct else 'reproducibility'} artifacts are present.",
        ))

    json_names = [
        name for name in (
            "package-manifest.json",
            "verification-report.json",
            "experiment.json",
            "reproducibility-manifest.json",
            "results.json",
            "evidence/experiment.json",
            "dataset-manifest.json",
            "environment.json",
            "model-metadata.json",
            "file-hashes.json",
            "audit-ledger.json",
            "notary-artifact.json",
        )
        if (root / name).is_file()
    ]
    parsed: Dict[str, Any] = {}
    try:
        for name in json_names:
            parsed[name] = _read_json(root / name)
    except ValueError as exc:
        results.append(_err("package_schema", str(exc)))
        return

    for name in ("package-manifest.json", "verification-report.json"):
        if name in parsed and not isinstance(parsed[name], dict):
            results.append(_err("package_schema", f"{name} must contain a JSON object."))
    for name in ("experiment.json", "results.json", "evidence/experiment.json"):
        if name in parsed:
            value = parsed[name]
            if not isinstance(value, dict) or not isinstance(value.get("experiment_id"), str):
                results.append(_err(
                    "package_schema",
                    f"{name} must be an object with a string experiment_id.",
                ))
    if "metrics.json" in expected and (root / "metrics.json").is_file():
        metrics = _read_json(root / "metrics.json")
        if not isinstance(metrics, dict):
            results.append(_err("package_schema", "metrics.json must contain a JSON object."))
    if "dataset-manifest.json" in parsed and not isinstance(parsed["dataset-manifest.json"], dict):
        results.append(_err("package_schema", "dataset-manifest.json must contain an object."))
    if "file-hashes.json" in parsed and not isinstance(parsed["file-hashes.json"], dict):
        results.append(_err("package_schema", "file-hashes.json must contain an object."))


def check_experiment_consistency(root: Path, results: List[Dict[str, str]]) -> None:
    """Cross-check exported result, report, metrics, and lineage metadata."""
    experiment_path = root / "experiment.json"
    results_path = root / "results.json"
    report_path = root / "verification-report.json"
    payload_path = experiment_path if experiment_path.is_file() else results_path
    if not payload_path.is_file():
        return
    try:
        payload = _read_json(payload_path)
        report = _read_json(report_path) if report_path.is_file() else None
    except ValueError as exc:
        results.append(_err("evidence_consistency", str(exc)))
        return
    if not isinstance(payload, dict):
        return

    issues: List[str] = []
    if isinstance(report, dict):
        if (root / "package-manifest.json").is_file():
            try:
                package_manifest = _read_json(root / "package-manifest.json")
            except ValueError as exc:
                issues.append(str(exc))
                package_manifest = None
            if isinstance(package_manifest, dict):
                version_fields = (
                    "evidence_format_version", "protocol_version", "schema_version",
                    "experiment_schema_version", "research_artifact_version",
                )
                for field in version_fields:
                    if report.get(field) != package_manifest.get(field):
                        issues.append(f"{field} differs between package manifest and verification report")
        if payload.get("experiment_id") != report.get("experiment_id"):
            issues.append("experiment_id differs between evidence and verification report")
        for field in ("result_hash", "configuration_hash", "status"):
            if payload.get(field) is not None and report.get(field) != payload.get(field):
                issues.append(f"{field} differs between evidence and verification report")

    run_manifest = payload.get("run_manifest")
    if isinstance(run_manifest, dict):
        if run_manifest.get("experiment_id") not in (None, payload.get("experiment_id")):
            issues.append("run_manifest experiment_id differs from evidence experiment_id")
        manifest_path = root / "reproducibility-manifest.json"
        if not manifest_path.is_file():
            manifest_path = root / "evidence" / "experiment.json"
        if manifest_path.name == "reproducibility-manifest.json" and manifest_path.is_file():
            try:
                exported_manifest = _read_json(manifest_path)
            except ValueError as exc:
                issues.append(str(exc))
            else:
                if exported_manifest != run_manifest:
                    issues.append("reproducibility-manifest.json differs from run_manifest")

    dataset_path = root / "dataset-manifest.json"
    dataset = run_manifest.get("dataset") if isinstance(run_manifest, dict) else None
    if dataset_path.is_file() and isinstance(dataset, dict):
        try:
            exported_dataset = _read_json(dataset_path)
        except ValueError as exc:
            issues.append(str(exc))
        else:
            if isinstance(exported_dataset, dict):
                declared = exported_dataset.get("sha256")
                lineage_hash = dataset.get("sha256")
                if declared and lineage_hash and declared != lineage_hash:
                    issues.append("dataset-manifest sha256 differs from run_manifest dataset sha256")

    metrics_path = root / "metrics.json"
    if not metrics_path.is_file():
        metrics_path = root / "metrics.csv"
    if metrics_path.name == "metrics.json" and metrics_path.is_file():
        try:
            if _read_json(metrics_path) != (payload.get("metrics") or payload.get("comparison") or {}):
                issues.append("metrics.json differs from experiment metrics")
        except ValueError as exc:
            issues.append(str(exc))
    elif metrics_path.name == "metrics.csv" and metrics_path.is_file():
        expected_metrics: Dict[str, str] = {}

        def flatten_metrics(value: Any, prefix: str = "") -> None:
            if isinstance(value, dict):
                for key, nested in value.items():
                    flatten_metrics(nested, f"{prefix}.{key}" if prefix else str(key))
            elif isinstance(value, bool):
                expected_metrics[prefix] = str(value)
            elif isinstance(value, (int, float)):
                expected_metrics[prefix] = str(round(float(value), 6))
            elif isinstance(value, str):
                expected_metrics[prefix] = value

        flatten_metrics(payload.get("metrics") or payload.get("comparison") or {})
        try:
            with metrics_path.open(newline="", encoding="utf-8") as stream:
                actual_metrics = {
                    row["metric"]: row["value"]
                    for row in csv.DictReader(stream)
                    if "metric" in row and "value" in row
                }
        except (OSError, UnicodeError, csv.Error) as exc:
            issues.append(f"Cannot read metrics.csv: {exc}")
        else:
            if actual_metrics != expected_metrics:
                issues.append("metrics.csv differs from experiment metrics")

    if issues:
        results.append(_err("evidence_consistency", "; ".join(issues)))
    else:
        results.append(_ok(
            "evidence_consistency",
            "Experiment identifiers, report fields, and available lineage artifacts agree.",
        ))

# ── checks ────────────────────────────────────────────────────────────────────
def check_version(
    check: str,
    artifact_type: str,
    version_field: Any,
    supported: List[str],
    results: List[Dict[str, str]],
    *,
    legacy_default: bool = True,
) -> bool:
    if version_field is None and legacy_default:
        version = "1"
    elif version_field is None:
        results.append(_err(
            check,
            f"{artifact_type} is missing required {check}.",
        ))
        return False
    elif isinstance(version_field, bool) or not isinstance(version_field, (str, int)):
        version = repr(version_field)
    else:
        version = str(version_field).strip()
    if version in supported:
        suffix = " (legacy default)" if version_field is None else ""
        results.append(_ok(check, f"{artifact_type} {check}={version} supported{suffix}."))
        return True
    results.append(_err(
        check,
        f"{artifact_type} {check}={version} not supported "
        f"(supported: {', '.join(supported)}).",
    ))
    return False


def check_protocol_version(artifact_type: str, version_field: Any,
                           results: List[Dict[str, str]]) -> None:
    """Check cryptographic protocol version; missing means legacy protocol v1."""
    check_version(
        "protocol_version", artifact_type, version_field,
        SUPPORTED_PROTOCOL_VERSIONS, results,
    )


def check_package_versions(root: Path, results: List[Dict[str, str]]) -> None:
    """Accept old packages without a manifest as evidence-format v1."""
    manifest_path = root / "package-manifest.json"
    if not manifest_path.exists():
        check_version(
            "evidence_format_version", "legacy package", None,
            SUPPORTED_EVIDENCE_FORMAT_VERSIONS, results,
        )
        check_version(
            "protocol_version", "legacy package", None,
            SUPPORTED_PROTOCOL_VERSIONS, results,
        )
        results.append(_ok("schema_version", "Legacy package schema defaults to version 1."))
        results.append(_ok(
            "experiment_schema_version",
            "Legacy experiment schema defaults to version 1.",
        ))
        results.append(_ok(
            "research_artifact_version",
            "Legacy research artifact format defaults to version 1.",
        ))
        return

    try:
        manifest = _loads_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        results.append(_err("package_manifest", f"Cannot read package-manifest.json: {exc}"))
        return
    if not isinstance(manifest, dict):
        results.append(_err("package_manifest", "package-manifest.json must contain an object."))
        return

    for field, supported in (
        ("evidence_format_version", SUPPORTED_EVIDENCE_FORMAT_VERSIONS),
        ("protocol_version", SUPPORTED_PROTOCOL_VERSIONS),
        ("schema_version", SUPPORTED_SCHEMA_VERSIONS),
        ("experiment_schema_version", SUPPORTED_EXPERIMENT_SCHEMA_VERSIONS),
        ("research_artifact_version", SUPPORTED_RESEARCH_ARTIFACT_VERSIONS),
    ):
        if field not in manifest:
            results.append(_err(field, f"package manifest is missing required field {field}."))
            continue
        is_supported = check_version(
            field, "package manifest", manifest[field], supported, results,
            legacy_default=False,
        )
        if (
            field == "evidence_format_version"
            and is_supported
            and str(manifest[field]).strip() != "2"
        ):
            results.append(_err(
                field,
                "A package containing package-manifest.json must use evidence_format_version=2.",
            ))


def check_file_hashes(root: Path, results: List[Dict[str, str]]) -> None:
    manifest_path = root / "file-hashes.json"
    if not manifest_path.exists():
        results.append(_warn("file_hashes", "No file-hashes.json — skipping artifact hash audit."))
        return
    try:
        manifest = _read_json(manifest_path)
    except ValueError as exc:
        results.append(_err("file_hashes", str(exc)))
        return
    if not isinstance(manifest, dict) or not manifest:
        results.append(_err("file_hashes", "file-hashes.json must be a non-empty object."))
        return
    bad, missing = [], []
    invalid = []
    declared_paths = set()
    for rel, declared in manifest.items():
        path = _safe_package_file(root, rel)
        if path is None:
            invalid.append(str(rel))
        elif not _is_sha256(declared):
            invalid.append(str(rel))
        elif not path.is_file():
            missing.append(rel)
        else:
            declared_paths.add(Path(rel).as_posix())
            if sha256_file(path) != declared:
                bad.append(rel)
    actual_paths = set()
    for path in root.rglob("*"):
        if path.is_file() and path != manifest_path:
            relative = path.relative_to(root).as_posix()
            resolved = _safe_package_file(root, relative)
            if resolved is None or not resolved.is_file():
                invalid.append(relative)
            else:
                actual_paths.add(relative)
    undeclared = sorted(actual_paths - declared_paths)
    if invalid:
        results.append(_err(
            "file_hashes",
            "Invalid relative path or SHA-256 digest in inventory: " + ", ".join(invalid),
        ))
    if missing:
        results.append(_err("file_hashes", f"Declared files missing: {', '.join(missing)}"))
    if bad:
        results.append(_err("file_hashes", f"Hash mismatch (modified after export): {', '.join(bad)}"))
    if undeclared:
        results.append(_err("file_hashes", f"Files omitted from inventory: {', '.join(undeclared)}"))
    if not missing and not bad and not invalid and not undeclared:
        results.append(_ok("file_hashes", f"All {len(manifest)} declared files match their hashes."))


def check_repro_package(root: Path, results: List[Dict[str, str]]) -> None:
    """Verify a reproducibility package: file-hashes.json (if present) plus
    recomputation of the declared result_hash from results.json."""
    check_file_hashes(root, results)

    results_path = root / "results.json"
    report_path = root / "verification-report.json"
    report = None
    if report_path.exists():
        try:
            report = _loads_json(report_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            results.append(_err(
                "verification_report",
                f"Cannot read verification-report.json: {exc}",
            ))
        else:
            is_legacy_format = not (root / "package-manifest.json").exists()
            if isinstance(report, dict):
                report_versions = (
                    ("evidence_format_version", SUPPORTED_EVIDENCE_FORMAT_VERSIONS),
                    ("protocol_version", SUPPORTED_PROTOCOL_VERSIONS),
                    ("schema_version", SUPPORTED_SCHEMA_VERSIONS),
                    ("experiment_schema_version", SUPPORTED_EXPERIMENT_SCHEMA_VERSIONS),
                    ("research_artifact_version", SUPPORTED_RESEARCH_ARTIFACT_VERSIONS),
                )
                for field, supported in report_versions:
                    check_version(
                        field, "verification-report", report.get(field), supported,
                        results, legacy_default=is_legacy_format,
                    )
                manifest_path = root / "package-manifest.json"
                if manifest_path.exists():
                    try:
                        package_manifest = _loads_json(
                            manifest_path.read_text(encoding="utf-8")
                        )
                    except (OSError, UnicodeError, ValueError):
                        package_manifest = None
                    if isinstance(package_manifest, dict):
                        for field, _ in report_versions:
                            report_value = report.get(field)
                            manifest_value = package_manifest.get(field)
                            equal = (
                                not isinstance(report_value, bool)
                                and not isinstance(manifest_value, bool)
                                and isinstance(report_value, (str, int))
                                and isinstance(manifest_value, (str, int))
                                and str(report_value).strip()
                                == str(manifest_value).strip()
                            )
                            if not equal:
                                results.append(_err(
                                    field,
                                    f"verification-report {field} does not match package manifest.",
                                ))
            else:
                results.append(_err(
                    "verification_report",
                    "verification-report.json must contain an object.",
                ))
    if not (results_path.exists() and report_path.exists()):
        results.append(_warn("repro_package", "Not a full reproducibility package (missing results.json or verification-report.json)."))
        return

    if not isinstance(report, dict):
        return
    declared = report.get("result_hash")
    if not declared:
        results.append(_warn("result_hash", "verification-report.json declares no result_hash."))
        return

    try:
        payload = _read_json(results_path)
    except ValueError as exc:
        results.append(_err("results", str(exc)))
        return
    if not isinstance(payload, dict):
        results.append(_err("results", "results.json must contain a JSON object."))
        return
    # The production result_hash covers the result with the research envelope
    # stripped.  Re-declared here (not imported) to keep this verifier
    # independent; test_reference_differential.py enforces the sync against
    # backend.app.services.experiment_service.RESEARCH_ENVELOPE_KEYS.
    envelope_keys = {
        "run_manifest", "result_hash", "configuration_hash",
        "trust_profile", "evidence_package", "timestamp", "reproducibility",
    }
    stripped = {k: v for k, v in payload.items() if k not in envelope_keys}
    recomputed = sha256_hex(canonical_json(stripped))
    if recomputed == declared:
        results.append(_ok("result_hash",
                           f"result_hash recomputes from results.json (envelope-stripped canonical digest)."))
    else:
        results.append(_err("result_hash",
                            f"declared={declared[:16]}… recomputed={recomputed[:16]}… — payload modified after export OR envelope keys differ."))
    evidence_path = root / "evidence" / "experiment.json"
    if evidence_path.is_file():
        try:
            evidence_payload = _read_json(evidence_path)
        except ValueError as exc:
            results.append(_err("evidence_lineage", str(exc)))
        else:
            if not isinstance(evidence_payload, dict):
                results.append(_err("evidence_lineage", "evidence/experiment.json must be an object."))
            elif evidence_payload != payload:
                results.append(_err(
                    "evidence_lineage",
                    "evidence/experiment.json does not match results.json.",
                ))
            else:
                results.append(_ok(
                    "evidence_lineage",
                    "evidence/experiment.json matches results.json.",
                ))


def check_audit_chain(root: Path, results: List[Dict[str, str]]) -> None:
    """Verify a sentinelcrypt.audit-ledger.v1 chain: JSON list of records with
    sequence_number / payload_json / previous_hash / record_hash."""
    path = root / "audit-ledger.json"
    if not path.exists():
        results.append(_warn("audit_chain", "No audit-ledger.json — skipping chain verification."))
        return
    try:
        data = _read_json(path)
    except ValueError as exc:
        results.append(_err("audit_chain", str(exc)))
        return
    records = data.get("records", data) if isinstance(data, dict) else data
    if not isinstance(records, list):
        results.append(_err("audit_chain", "audit-ledger.json is not a list of records."))
        return
    check_protocol_version("audit-ledger", data.get("protocol_version") if isinstance(data, dict) else None, results)

    genesis = "0" * 64
    expected_prev = genesis
    failures: List[str] = []
    prev_seq: Optional[int] = None
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            failures.append(f"record {i} is not an object")
            continue
        seq = rec.get("sequence_number")
        if isinstance(seq, bool) or not isinstance(seq, int):
            failures.append(f"record {i} has an invalid sequence_number")
            continue
        expected_seq = 1 if prev_seq is None else prev_seq + 1
        if seq != expected_seq:
            failures.append(f"sequence mismatch at record {i}: expected {expected_seq}, found {seq}")
        prev_seq = seq
        previous_hash = rec.get("previous_hash")
        stored_hash = rec.get("record_hash")
        if not _is_sha256(previous_hash) or not _is_sha256(stored_hash):
            failures.append(f"record {i} (seq {seq}): malformed hash field")
            continue
        if previous_hash != expected_prev:
            failures.append(f"record {i} (seq {seq}): previous_hash does not link")
        try:
            payload = _loads_json(rec["payload_json"])
            recomputed_payload_hash = sha256_hex(canonical_json(payload))
            recomputed_record = sha256_hex(previous_hash + recomputed_payload_hash)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            failures.append(f"record {i} (seq {seq}): invalid payload ({exc})")
            expected_prev = stored_hash
            continue
        if recomputed_record != stored_hash:
            failures.append(f"record {i} (seq {seq}): record_hash mismatch — payload modified")
        expected_prev = stored_hash
    if failures:
        results.append(_err("audit_chain", f"{len(failures)} chain failure(s): " + "; ".join(failures[:5])))
    else:
        results.append(_ok("audit_chain", f"Chain of {len(records)} records verifies (genesis → tip)."))


def check_notary_artifact(root: Path, results: List[Dict[str, str]]) -> None:
    """Verify a notary artifact (Ed25519 over canonical payload digest).

    Ed25519 support is imported only when a signed artifact is present. If the
    optional verifier dependency is unavailable, verification fails closed.
    """
    path = root / "notary-artifact.json"
    if not path.exists():
        results.append(_warn("notary", "No notary-artifact.json — skipping signature verification."))
        return
    try:
        artifact = _read_json(path)
    except ValueError as exc:
        results.append(_err("notary", str(exc)))
        return
    if not isinstance(artifact, dict):
        results.append(_err("notary", "notary-artifact.json must contain a JSON object."))
        return
    required = {"payload", "payload_hash", "signature", "public_key"}
    missing_fields = sorted(required - set(artifact))
    if missing_fields:
        results.append(_err(
            "package_schema",
            "notary-artifact.json is missing required fields: " + ", ".join(missing_fields),
        ))
        return
    if artifact.get("algorithm", "Ed25519") != "Ed25519":
        results.append(_err("package_schema", "notary algorithm must be Ed25519."))
        return
    if artifact.get("digest_algorithm", "SHA-256") != "SHA-256":
        results.append(_err("package_schema", "notary digest_algorithm must be SHA-256."))
        return
    if not _is_sha256(artifact.get("payload_hash")):
        results.append(_err(
            "package_schema",
            "notary payload_hash must be 64 lowercase hexadecimal characters.",
        ))
        return
    if not isinstance(artifact.get("public_key"), str) or not isinstance(artifact.get("signature"), str):
        results.append(_err(
            "package_schema",
            "notary public_key and signature must be base64 strings.",
        ))
        return
    check_protocol_version("notary-artifact", artifact.get("protocol_version"), results)
    check_version(
        "schema_version", "notary-artifact", artifact.get("schema_version"),
        SUPPORTED_SCHEMA_VERSIONS, results,
    )
    check_version(
        "research_artifact_version", "notary-artifact",
        artifact.get("research_artifact_version"),
        SUPPORTED_RESEARCH_ARTIFACT_VERSIONS, results,
    )
    expected_type = "sentinelcrypt.research-artifact.v1"
    actual_type = artifact.get("artifact_type", expected_type)
    if actual_type != expected_type:
        results.append(_err(
            "research_artifact_version",
            f"Unsupported artifact_type={actual_type!r}.",
        ))

    payload = artifact.get("payload")
    try:
        digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    except (TypeError, ValueError) as exc:
        results.append(_err("notary_digest", f"Payload cannot be canonicalized: {exc}"))
        return
    if digest == artifact.get("payload_hash"):
        results.append(_ok("notary_digest", "payload digest recomputes from the embedded payload."))
    else:
        results.append(_err("notary_digest",
                            f"digest mismatch: declared={artifact.get('payload_hash', '')[:16]}… recomputed={digest[:16]}…"))
        return  # signature over a different digest is meaningless

    pub_b64 = artifact.get("public_key", "")
    sig_b64 = artifact.get("signature", "")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # optional
    except ImportError:
        results.append(_err(
            "notary_signature",
            "`cryptography` is required to verify this signature; signature was NOT verified.",
        ))
        return
    try:
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_b64, validate=True))
        signature = base64.b64decode(sig_b64, validate=True)
        if len(signature) != 64:
            raise ValueError("Ed25519 signature must be 64 bytes")
        pub.verify(signature, bytes.fromhex(digest))
        results.append(_ok("notary_signature", "Ed25519 signature valid for the embedded public key."))
    except (ValueError, TypeError) as exc:
        results.append(_err("notary_signature", f"signature encoding invalid: {exc}"))
    except Exception as exc:
        results.append(_err("notary_signature", f"signature invalid: {exc.__class__.__name__}"))


def check_direct_result_hash(root: Path, results: List[Dict[str, str]]) -> None:
    """Recompute the result digest for standard experiment evidence exports."""
    path = root / "experiment.json"
    if not path.is_file():
        return
    try:
        payload = _read_json(path)
    except ValueError as exc:
        results.append(_err("result_hash", str(exc)))
        return
    if not isinstance(payload, dict):
        return
    declared = payload.get("result_hash")
    if declared is None:
        results.append(_warn("result_hash", "experiment.json does not declare result_hash."))
        return
    if not _is_sha256(declared):
        results.append(_err("result_hash", "experiment.json result_hash must be 64 lowercase hex characters."))
        return
    envelope_keys = {
        "run_manifest", "result_hash", "configuration_hash",
        "trust_profile", "evidence_package", "timestamp", "reproducibility",
    }
    stripped = {key: value for key, value in payload.items() if key not in envelope_keys}
    computed = sha256_hex(canonical_json(stripped))
    if computed == declared:
        results.append(_ok("result_hash", "result_hash recomputes from experiment.json."))
    else:
        results.append(_err(
            "result_hash",
            f"experiment.json result_hash mismatch: declared={declared[:16]}… recomputed={computed[:16]}…",
        ))


# ── driver ────────────────────────────────────────────────────────────────────
def verify_directory(root: Path) -> Dict[str, Any]:
    results: List[Dict[str, str]] = []
    if not root.is_dir():
        return {
            "verified": False,
            "status": "INVALID_FORMAT",
            "error": f"Not a directory: {root}",
            "package": str(root),
            "summary": {"pass": 0, "warn": 0, "fail": 1},
            "results": [_err("package_present", f"Not a directory: {root}")],
        }
    results.append(_ok("package_present", f"Verifying evidence package at {root}"))
    try:
        check_package_structure(root, results)
        check_package_versions(root, results)
        check_repro_package(root, results)
        check_experiment_consistency(root, results)
        check_direct_result_hash(root, results)
        if (root / "experiment.json").is_file():
            check_file_hashes(root, results)
        check_audit_chain(root, results)
        check_notary_artifact(root, results)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        results.append(_err(
            "package_format",
            f"Package contains malformed or unreadable evidence: {exc.__class__.__name__}: {exc}",
        ))

    hard_fail = [r for r in results if r["status"] == "FAIL"]
    hard_pass = [r for r in results if r["status"] == "PASS"]
    unsupported = any(
        item["status"] == "FAIL"
        and item["detail"].find("not supported") >= 0
        and item["check"] in {
            "evidence_format_version", "protocol_version", "schema_version",
            "experiment_schema_version", "research_artifact_version",
        }
        for item in results
    )
    invalid_format = any(
        item["status"] == "FAIL"
        and (
            item["check"] in {
                "package_present", "package_structure", "artifact_presence",
                "package_schema", "package_manifest", "package_format",
            }
            or "missing required" in item["detail"]
        )
        for item in results
    )
    status = (
        "UNSUPPORTED_VERSION" if unsupported
        else "INVALID_FORMAT" if invalid_format
        else "FAILED" if hard_fail
        else "VERIFIED"
    )
    return {
        "verified": status == "VERIFIED" and len(hard_pass) > 0,
        "status": status,
        "exit_code": {
            "VERIFIED": 0,
            "FAILED": 1,
            "INVALID_FORMAT": 2,
            "UNSUPPORTED_VERSION": 3,
        }[status],
        "protocol_versions_supported": SUPPORTED_PROTOCOL_VERSIONS,
        "evidence_format_versions_supported": SUPPORTED_EVIDENCE_FORMAT_VERSIONS,
        "schema_versions_supported": SUPPORTED_SCHEMA_VERSIONS,
        "experiment_schema_versions_supported": SUPPORTED_EXPERIMENT_SCHEMA_VERSIONS,
        "research_artifact_versions_supported": SUPPORTED_RESEARCH_ARTIFACT_VERSIONS,
        "package": str(root),
        "summary": {"pass": len(hard_pass), "warn": sum(1 for r in results if r["status"] == "WARN"),
                    "fail": len(hard_fail)},
        "results": results,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sentinel-verify",
        description="Independently verify a SentinelCrypt evidence package offline.",
    )
    parser.add_argument("package", help="Path to the evidence/reproducibility package directory")
    parser.add_argument(
        "--json", action="store_true",
        help="Machine-readable JSON output (default: human-readable)",
    )
    args = parser.parse_args(argv)

    report = verify_directory(Path(args.package))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"sentinel-verify — {report['package']}")
        print("=" * 60)
        for r in report["results"]:
            mark = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]"}[r["status"]]
            print(f"{mark} {r['check']:<20} {r['detail']}")
        print("=" * 60)
        s = report["summary"]
        print(f"{report['status']}   "
              f"(pass={s['pass']} warn={s['warn']} fail={s['fail']})")
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
