"""Tests for reproducibility manifests and package export."""
import json

import pytest

from backend.app.research.reproducibility import (
    build_manifest,
    compare_manifests,
    export_reproducibility_package,
    flatten_metrics,
    PACKAGE_FILES,
)
from backend.app.cryptography.versioning import version_metadata


def test_manifest_captures_environment():
    manifest = build_manifest(random_seed=42,
                              model_config={"model_type": "random_forest"})
    assert manifest["os"]["system"]
    assert manifest["python"]["version"]
    assert manifest["cpu"]["cpu_count"]
    assert "numpy" in manifest["packages"]
    assert manifest["random_seed"] == 42
    assert manifest["git"]["commit"]
    assert "sha256" in manifest["dataset"]


def test_compare_manifests_cosmetic_difference_only():
    a = build_manifest(random_seed=7)
    b = dict(a)
    b["generated_at"] = "2000-01-01T00:00:00Z"  # wall-clock drift only
    report = compare_manifests(a, b)
    assert report["identical"] is False  # timestamp differs
    assert report["environment_comparable"] is True
    assert report["critical_differences"] == []


def test_compare_manifests_detects_seed_change():
    a = build_manifest(random_seed=42)
    b = build_manifest(random_seed=43)
    report = compare_manifests(a, b)
    assert report["identical"] is False
    fields = {d["field"] for d in report["differences"]}
    assert "random_seed" in fields
    assert report["environment_comparable"] is False


def test_flatten_metrics_rows():
    rows = flatten_metrics({"a": {"b": 1.25}, "c": 2, "note": "text", "flag": True})
    by_metric = {r["metric"]: r["value"] for r in rows}
    assert by_metric["a.b"] == 1.25
    assert by_metric["c"] == 2.0
    assert by_metric["note"] == "text"
    assert by_metric["flag"] == "True"


def test_export_package_creates_all_files(tmp_path):
    from backend.app.services.experiment_service import ExperimentService
    service = ExperimentService()
    result = service.run_exp_d({"n_samples": 300, "random_state": 42})
    package = export_reproducibility_package(
        "EXP-D", result, {"n_samples": 300, "random_state": 42},
        out_root=tmp_path / "pkg",
    )
    assert set(package["files"]) >= set(PACKAGE_FILES)
    assert {key: package[key] for key in version_metadata()} == version_metadata()
    for name in package["files"]:
        assert (tmp_path / "pkg" / name).exists()
    package_manifest = json.loads(
        (tmp_path / "pkg" / "package-manifest.json").read_text()
    )
    verification_report = json.loads(
        (tmp_path / "pkg" / "verification-report.json").read_text()
    )
    assert {key: package_manifest[key] for key in version_metadata()} == version_metadata()
    assert {key: verification_report[key] for key in version_metadata()} == version_metadata()
    assert len(package["package_hash"]) == 64
    # config.yaml parses and metrics.csv has rows
    import yaml
    config = yaml.safe_load((tmp_path / "pkg" / "config.yaml").read_text())
    assert config["experiment_id"] == "EXP-D"
    metrics_csv = (tmp_path / "pkg" / "metrics.csv").read_text()
    assert "metric,value" in metrics_csv


def test_package_hash_changes_when_result_changes(tmp_path):
    from backend.app.services.experiment_service import ExperimentService
    service = ExperimentService()
    result = service.run_exp_d({"n_samples": 300, "random_state": 42})
    p1 = export_reproducibility_package("EXP-D", result, {},
                                        out_root=tmp_path / "p1")
    p2 = export_reproducibility_package("EXP-D", result, {},
                                        out_root=tmp_path / "p2")
    # same inputs -> identical package hash (modulo timestamps in README only)
    assert p1["package_hash"] == p2["package_hash"]


def test_package_declares_reproduction_steps(tmp_path):
    from backend.app.services.experiment_service import ExperimentService
    service = ExperimentService()
    result = service.run_exp_a({"n_samples": 250, "random_state": 42})
    export_reproducibility_package("EXP-A", result, {}, out_root=tmp_path / "p3")
    instructions = (tmp_path / "p3" / "reproduction-instructions.md").read_text()
    assert "git.commit" in instructions
    assert "result_hash" in instructions
