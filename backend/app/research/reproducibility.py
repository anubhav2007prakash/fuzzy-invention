"""Reproducibility manifest + package export (items: cross-environment manifest,
one-click reproducibility package, determinism report).

Single owner of environment capture:
    OS / Python / CPU / RAM / package versions / dataset hash /
    model configuration / random seed / git commit
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from backend.app.core.config import settings
from backend.app.cryptography.hashing import hash_file, sha256_hash
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.versioning import version_metadata

PACKAGE_FILES = [
    "README.md",
    "package-manifest.json",
    "config.yaml",
    "dataset-manifest.json",
    "environment.json",
    "results.json",
    "metrics.csv",
    "model-metadata.json",
    "evidence/experiment.json",
    "verification-report.json",
    "reproduction-instructions.md",
]


def _package_versions() -> Dict[str, str]:
    versions: Dict[str, str] = {}
    for module in ("numpy", "pandas", "sklearn", "scipy", "shap", "fastapi", "sqlalchemy", "cryptography"):
        try:
            mod = __import__(module)
            versions[module] = getattr(mod, "__version__", "unknown")
        except Exception:
            versions[module] = "not-installed"
    return versions


def _cpu_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "processor": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
    }
    try:
        with open("/proc/cpuinfo") as f:  # Linux
            for line in f:
                if line.startswith("model name"):
                    info["model"] = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    return info


def _memory_total_mb() -> Optional[float]:
    try:
        import psutil  # optional
        return round(psutil.virtual_memory().total / (1024 * 1024), 1)
    except Exception:
        pass
    try:  # Windows
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):  # type: ignore[attr-defined]
            return round(stat.ullTotalPhys / (1024 * 1024), 1)
    except Exception:
        pass
    return None


def git_metadata() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3]

    def run_git(args: List[str]) -> str:
        return subprocess.check_output(
            ["git", *args], cwd=repo_root, stderr=subprocess.DEVNULL, text=True, timeout=2,
        ).strip()

    try:
        return {
            "commit": run_git(["rev-parse", "--short", "HEAD"]),
            "branch": run_git(["rev-parse", "--abbrev-ref", "HEAD"]),
            "dirty_worktree": bool(run_git(["status", "--short"])),
        }
    except Exception:
        return {"commit": "unknown", "branch": "unknown", "dirty_worktree": None}


def build_manifest(
    dataset_id: Optional[str] = None,
    dataset_hash: Optional[str] = None,
    model_config: Optional[Dict[str, Any]] = None,
    random_seed: int = 42,
    db=None,
) -> Dict[str, Any]:
    """Full cross-environment manifest (item: compare results across environments)."""
    resolved_dataset_hash = dataset_hash
    if resolved_dataset_hash is None and dataset_id and db is not None:
        from backend.app.db.repositories.dataset_repository import DatasetRepository
        dataset = DatasetRepository(db).get_by_id(dataset_id)
        if dataset:
            resolved_dataset_hash = dataset.file_hash

    if resolved_dataset_hash is None:
        raw_dir = Path(settings.DATA_RAW_DIR)
        csvs = sorted(raw_dir.glob("*.csv"))
        if csvs:
            resolved_dataset_hash = hash_file(str(csvs[0]))

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "platform": platform.platform(),
        },
        "python": {
            "version": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "cpu": _cpu_info(),
        "memory_total_mb": _memory_total_mb(),
        "packages": _package_versions(),
        "dataset": {
            "id": dataset_id,
            "sha256": resolved_dataset_hash,
        },
        "model_configuration": model_config or {},
        "random_seed": random_seed,
        "git": git_metadata(),
    }


def compare_manifests(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Field-level diff of two manifests → what differed across environments."""
    differences: List[Dict[str, str]] = []
    matched: List[str] = []

    def walk(x: Any, y: Any, path: str) -> None:
        if isinstance(x, dict) and isinstance(y, dict):
            for key in sorted(set(x) | set(y)):
                walk(x.get(key), y.get(key), f"{path}.{key}" if path else str(key))
        elif x != y:
            differences.append({"field": path, "a": str(x), "b": str(y)})
        else:
            matched.append(path)

    walk(a, b, "")
    reproducible_keys = ("python.version", "packages", "random_seed", "dataset.sha256",
                         "model_configuration", "git.commit")
    critical_differences = [d for d in differences if d["field"].startswith(reproducible_keys)]
    return {
        "identical": not differences,
        "n_matched": len(matched),
        "n_differences": len(differences),
        "differences": differences,
        "critical_differences": critical_differences,
        "environment_comparable": not critical_differences,
        "interpretation": (
            "Manifests are byte-identical."
            if not differences
            else (
                "Reproduction-critical fields differ (seed/code/dataset/packages); "
                "result differences cannot be attributed to the environment alone."
                if critical_differences
                else "Only cosmetic differences (timestamps/hostnames); results should reproduce."
            )
        ),
    }


def flatten_metrics(obj: Any, prefix: str = "") -> List[Dict[str, Any]]:
    """Flatten nested metric dict to rows of (metric, value) for metrics.csv."""
    rows: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(flatten_metrics(value, path))
    elif isinstance(obj, bool):
        rows.append({"metric": prefix, "value": str(obj)})
    elif isinstance(obj, (int, float)):
        rows.append({"metric": prefix, "value": round(float(obj), 6)})
    elif isinstance(obj, str):
        rows.append({"metric": prefix, "value": obj})
    return rows


def export_reproducibility_package(
    experiment_id: str,
    result: Dict[str, Any],
    config: Dict[str, Any],
    out_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Write the full reproducibility package tree (item: one-click export)."""
    root = Path(out_root or (settings.RESULTS_DIR / "reproducibility" / experiment_id))
    (root / "evidence").mkdir(parents=True, exist_ok=True)
    (root / "plots").mkdir(parents=True, exist_ok=True)

    manifest = result.get("run_manifest") or build_manifest(
        model_config=config, random_seed=int(config.get("random_state", 42))
    )
    versions = version_metadata()
    (root / "package-manifest.json").write_text(
        json.dumps(
            {
                **versions,
                "experiment_id": experiment_id,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    metrics = result.get("metrics") or result.get("comparison") or {}
    # The package must be a pure function of (result, config): every embedded
    # timestamp derives from the result's own run stamp, NOT the export
    # wall-clock — otherwise two exports of the same result produce different
    # package hashes whenever a second boundary falls between them.
    generated = result.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # README
    (root / "README.md").write_text(
        f"# Reproducibility Package — {experiment_id}\n\n"
        f"Generated: {generated}\n\n"
        f"Result hash: `{result.get('result_hash', 'n/a')}`\n"
        f"Configuration hash: `{result.get('configuration_hash', 'n/a')}`\n\n"
        f"{result.get('title', experiment_id)}\n\n"
        "Synthetic-scope experiments use labelled synthetic data; see "
        "`dataset-manifest.json` for the dataset scope disclaimer.\n",
        encoding="utf-8",
    )

    # config.yaml (pyyaml)
    import yaml
    (root / "config.yaml").write_text(
        yaml.safe_dump(
            {"experiment_id": experiment_id, "configuration": config,
             "random_seed": config.get("random_state", 42)},
            sort_keys=True, default_flow_style=False,
        ),
        encoding="utf-8",
    )

    # dataset manifest
    dataset_manifest = {
        "scope": manifest.get("dataset_scope", "synthetic"),
        "disclaimer": manifest.get(
            "dataset_disclaimer",
            "Synthetic network-flow data with controlled properties.",
        ),
        "sha256": (manifest.get("dataset") or {}).get("sha256"),
        "dataset_id": (manifest.get("dataset") or {}).get("id"),
    }
    (root / "dataset-manifest.json").write_text(
        json.dumps(dataset_manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    # environment
    env = manifest.get("environment") or build_manifest()["python"]
    environment = build_manifest(
        model_config=config, random_seed=int(config.get("random_state", 42))
    )
    environment["generated_at"] = generated  # volatile wall-clock → result stamp
    environment["experiment_environment_subset"] = env
    (root / "environment.json").write_text(
        json.dumps(environment, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )

    # results + metrics.csv
    (root / "results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    rows = flatten_metrics(metrics)
    with open(root / "metrics.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["metric", "value"])
        writer.writeheader()
        writer.writerows(rows)

    # model metadata
    (root / "model-metadata.json").write_text(
        json.dumps({
            "experiment_id": experiment_id,
            "configuration": config,
            "parameters": result.get("parameters", {}),
            "random_seed": config.get("random_state"),
        }, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

    # evidence (canonical copy of the result) + verification report
    (root / "evidence" / "experiment.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    verification = {
        **versions,
        "experiment_id": experiment_id,
        "result_hash": result.get("result_hash"),
        "configuration_hash": result.get("configuration_hash"),
        "trust_profile": result.get("trust_profile", []),
        "generated_at": generated,
        "status": result.get("status"),
    }
    (root / "verification-report.json").write_text(
        json.dumps(verification, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )

    # reproduction instructions
    (root / "reproduction-instructions.md").write_text(
        f"# Reproducing {experiment_id}\n\n"
        "1. Clone the repository at the commit recorded in `environment.json` (`git.commit`).\n"
        "2. Install pinned packages from `environment.json` (`packages`).\n"
        "3. `alembic upgrade head`\n"
        f"4. `python scripts/sentinel.py experiment run {experiment_id}` "
        "with the configuration in `config.yaml`.\n"
        "5. Compare your `results.json` `result_hash` against the recorded value; "
        "identical canonical hashes indicate a bit-reproducible run.\n",
        encoding="utf-8",
    )

    # plots placeholder index (plot generation is done by the benchmark CLI step)
    (root / "plots" / "README.md").write_text(
        "Plot artifacts are generated by `scripts/sentinel.py experiment run --plots`.\n",
        encoding="utf-8",
    )

    # file hashes + package hash — also emitted as file-hashes.json so the
    # standalone sentinel-verify CLI can audit every declared file offline.
    file_hashes: Dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            file_hashes[str(path.relative_to(root).as_posix())] = hash_file(str(path))
    (root / "file-hashes.json").write_text(
        json.dumps(file_hashes, indent=2, sort_keys=True), encoding="utf-8"
    )
    file_hashes["file-hashes.json"] = hash_file(str(root / "file-hashes.json"))
    package_hash = sha256_hash(canonicalize({"files": file_hashes}))

    return {
        **versions,
        "experiment_id": experiment_id,
        "package_path": root.as_posix(),
        "files": sorted(file_hashes),
        "file_hashes": file_hashes,
        "package_hash": package_hash,
        "generated_at": generated,
    }
