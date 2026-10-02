"""Experiment Service — Orchestrates and executes research benchmark experiments EXP-A to EXP-D."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    build_audit_record_hashes,
    calculate_payload_hash,
    calculate_record_hash,
)
from backend.app.cryptography.hashing import hash_file, sha256_hash
from backend.app.cryptography.versioning import (
    EXPERIMENT_SCHEMA_VERSION,
    version_metadata,
)
from backend.app.cryptography.verifier import verify_ledger
from backend.app.ml.data.synthetic import generate_flow_dataset
from backend.app.ml.models.random_forest import RandomForestDetector
from backend.app.xai.shap_explainer import SHAPExplainer
from backend.app.xai.stability import ExplanationStabilityAnalyzer

RESULTS_DIR = Path(settings.RESULTS_DIR)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

EXPERIMENT_RESULT_FILES = {
    "EXP-A": "exp_a_cross_dataset.json",
    "EXP-B": "exp_b_xai_stability.json",
    "EXP-C": "exp_c_ledger_integrity.json",
    "EXP-D": "exp_d_model_comparison.json",
    "EXP-F": "exp_f_ablation_v2.json",
    "EXP-G": "exp_g_integrity_comparison.json",
    "EXP-H": "exp_h_xai_agreement.json",
    "EXP-ROBUSTNESS": "exp_robustness.json",
    "EXP-CALIBRATION": "exp_calibration.json",
}

EXPERIMENT_META = [
    {"id": "EXP-A", "title": "Cross-Dataset Generalization Gap"},
    {"id": "EXP-B", "title": "XAI Attribution Stability under Perturbation"},
    {"id": "EXP-C", "title": "Cryptographic Audit Integrity & Tamper Attacks"},
    {"id": "EXP-D", "title": "Model Architecture & Runtime Overhead Comparison"},
    {"id": "EXP-F", "title": "Component Ablation Study"},
    {"id": "EXP-G", "title": "Cryptographic Integrity Architecture Comparison"},
    {"id": "EXP-H", "title": "Cross-Method Explanation Agreement"},
    {"id": "EXP-ROBUSTNESS", "title": "Bounded-Perturbation Sensitivity Measurements"},
    {"id": "EXP-CALIBRATION", "title": "Prediction Probability Calibration Laboratory"},
]

KNOWN_EXPERIMENT_IDS = tuple(meta["id"] for meta in EXPERIMENT_META)


def result_artifact_name(exp_id: str) -> Optional[str]:
    """Result JSON filename for a core experiment or a registered plugin experiment."""
    normalized = exp_id.upper().strip()
    if normalized in EXPERIMENT_RESULT_FILES:
        return EXPERIMENT_RESULT_FILES[normalized]
    plugin = _lookup_experiment_plugin(normalized)
    if plugin is None:
        return None
    from backend.app.plugins.host import plugin_result_filename

    plugin_exp_id = str(plugin.metadata.get("experiment_id") or plugin.name).upper()
    return plugin_result_filename(plugin_exp_id)


def _lookup_experiment_plugin(exp_id: str):
    from backend.app.plugins.registry import get_registry

    registry = get_registry()
    key = str(exp_id).strip().lower()
    info = registry.get("experiment", key)
    if info is not None:
        return info
    want = str(exp_id).strip().upper()
    for item in registry.list("experiment"):
        meta_id = str(item.get("metadata", {}).get("experiment_id") or "").upper()
        if meta_id == want or item["name"].upper() == want:
            return registry.get("experiment", item["name"])
    return None


def _list_experiment_plugins():
    from backend.app.plugins.registry import get_registry

    return get_registry().list("experiment")

RESEARCH_ENVELOPE_KEYS = {
    "run_manifest",
    "result_hash",
    "configuration_hash",
    "trust_profile",
    "evidence_package",
    # wall-clock fields are NOT scientific content: identical configurations in
    # identical environments must produce identical result hashes (reproducibility)
    "timestamp",
    "reproducibility",
}

SYNTHETIC_DATA_DISCLAIMER = (
    "Current benchmark results use deterministic synthetic network-flow data with controlled properties. "
    "They are not real UNSW-NB15 or CICIDS2017 measurements."
)


def _reproducibility_metadata() -> Dict[str, Any]:
    """Collect reproducibility metadata for experiment results."""
    try:
        import shap as shap_lib
        shap_version = shap_lib.__version__
    except (ImportError, AttributeError):
        shap_version = "unknown"
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "sklearn_version": sklearn.__version__,
        "shap_version": shap_version,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


class ExperimentService:
    """Provides execution and persistence of reproducible research experiments."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # Helper: Synthetic Flow Generator for Deterministic Benchmarks
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def generate_synthetic_flow_dataset(
        n_samples: int = 1000,
        random_state: int = 42,
        shift_scale: float = 1.0,
        attack_ratio: float = 0.3,
        missing_rate: float = 0.0,
    ) -> pd.DataFrame:
        """Generate synthetic network-flow data (delegates to the shared generator).

        Single source of truth: backend.app.ml.data.synthetic — used by tests,
        benchmarks, and the Datasets synthetic-upload path alike.
        """
        return generate_flow_dataset(
            n_samples=n_samples,
            random_state=random_state,
            shift_scale=shift_scale,
            attack_ratio=attack_ratio,
            missing_rate=missing_rate,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Research Envelope: Validation, Canonical Hashes, Manifest, Trust Profile
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _positive_int(value: Any, field_name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be a positive integer.")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be a positive integer.") from None
        if parsed <= 0:
            raise ValueError(f"{field_name} must be a positive integer.")
        return parsed

    @staticmethod
    def _integer(value: Any, field_name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be an integer.")
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be an integer.") from None

    @staticmethod
    def _positive_float_list(value: Any, field_name: str) -> List[float]:
        if not isinstance(value, list) or not value:
            raise ValueError(f"{field_name} must be a non-empty list of positive numbers.")
        parsed: List[float] = []
        for item in value:
            try:
                number = float(item)
            except (TypeError, ValueError):
                raise ValueError(f"{field_name} must contain only positive numbers.") from None
            if not np.isfinite(number) or number <= 0:
                raise ValueError(f"{field_name} must contain only positive numbers.")
            parsed.append(number)
        return parsed

    def validate_experiment_config(self, exp_id: str, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate and normalize experiment configuration, raising ValueError naming bad fields."""
        normalized_id = exp_id.upper().strip()
        raw = config or {}

        if normalized_id == "EXP-A":
            return {
                "n_samples": self._positive_int(raw.get("n_samples", 1200), "n_samples"),
                "random_state": self._integer(raw.get("random_state", 42), "random_state"),
            }
        if normalized_id == "EXP-B":
            return {
                "noise_levels": self._positive_float_list(raw.get("noise_levels", [0.01, 0.05, 0.10, 0.20]), "noise_levels"),
                "n_repetitions": self._positive_int(raw.get("n_repetitions", 8), "n_repetitions"),
                "random_state": self._integer(raw.get("random_state", 42), "random_state"),
            }
        if normalized_id == "EXP-C":
            return {
                "n_blocks": self._positive_int(raw.get("n_blocks", 50), "n_blocks"),
                "random_state": self._integer(raw.get("random_state", 42), "random_state"),
            }
        if normalized_id == "EXP-D":
            return {
                "n_samples": self._positive_int(raw.get("n_samples", 1500), "n_samples"),
                "random_state": self._integer(raw.get("random_state", 42), "random_state"),
            }
        if normalized_id == "EXP-F":
            variant_list = raw.get("variants")
            if variant_list is not None and (
                not isinstance(variant_list, list) or not variant_list
            ):
                raise ValueError("variants must be a non-empty list.")
            if variant_list is not None and not all(
                isinstance(variant, str) for variant in variant_list
            ):
                raise ValueError("variants must contain only strings.")
            model_type = str(raw.get("model_type", "random_forest"))
            if model_type not in {"random_forest", "logistic_regression"}:
                raise ValueError(
                    "model_type must be 'random_forest' or 'logistic_regression'."
                )
            sample_count = self._positive_int(raw.get("n_samples", 1200), "n_samples")
            if sample_count < 40:
                raise ValueError("n_samples must be at least 40 for stratified ablation.")
            return {
                "n_samples": sample_count,
                "random_state": self._integer(raw.get("random_state", 42), "random_state"),
                "model_type": model_type,
                "repeats": self._positive_int(raw.get("repeats", 3), "repeats"),
                "explanation_samples": self._positive_int(
                    raw.get("explanation_samples", 1), "explanation_samples"
                ),
                **({"variants": variant_list} if variant_list else {}),
            }
        if normalized_id == "EXP-G":
            sizes = raw.get("sizes")
            if sizes is not None:
                if not isinstance(sizes, list) or not sizes:
                    raise ValueError("sizes must be a non-empty list of positive integers.")
                for s in sizes:
                    self._positive_int(s, "sizes")
            return {
                "random_state": self._integer(raw.get("random_state", 42), "random_state"),
                **({"sizes": [int(s) for s in sizes]} if sizes else {}),
            }
        if normalized_id == "EXP-H":
            levels = raw.get("noise_levels")
            if levels is not None:
                if not isinstance(levels, list) or not levels:
                    raise ValueError("noise_levels must be a non-empty list.")
                for lv in levels:
                    try:
                        value = float(lv)
                    except (TypeError, ValueError):
                        raise ValueError("noise_levels must contain only numbers.") from None
                    if value < 0:
                        raise ValueError("noise_levels must be non-negative.")
            return {
                "n_samples": self._positive_int(raw.get("n_samples", 800), "n_samples"),
                "random_state": self._integer(raw.get("random_state", 42), "random_state"),
                "top_k": self._positive_int(raw.get("top_k", 5), "top_k"),
                "model_type": str(raw.get("model_type", "random_forest")),
                **({"noise_levels": [float(l) for l in levels]} if levels else {}),
            }
        if normalized_id == "EXP-ROBUSTNESS":
            from backend.app.research.robustness import (
                DEFAULT_EPSILON_LEVELS,
                MAX_EPSILON,
                SUPPORTED_MODELS,
            )

            sample_count = self._positive_int(raw.get("n_samples", 800), "n_samples")
            if sample_count < 40 or sample_count > 10000:
                raise ValueError("n_samples must be between 40 and 10000.")
            n_probe = self._positive_int(raw.get("n_probe", 12), "n_probe")
            if n_probe > 100:
                raise ValueError("n_probe must not exceed 100.")
            n_repeats = self._positive_int(raw.get("n_repeats", 3), "n_repeats")
            if n_repeats > 10:
                raise ValueError("n_repeats must not exceed 10.")
            levels = self._positive_float_list(
                raw.get("epsilon_levels", DEFAULT_EPSILON_LEVELS),
                "epsilon_levels",
            )
            if len(levels) > 10:
                raise ValueError("epsilon_levels must contain at most 10 conditions.")
            if len(set(levels)) != len(levels):
                raise ValueError("epsilon_levels must contain unique values.")
            if any(level > MAX_EPSILON for level in levels):
                raise ValueError(
                    f"epsilon_levels must not exceed the maximum of {MAX_EPSILON}."
                )
            model_type = str(raw.get("model_type", "random_forest"))
            if model_type not in SUPPORTED_MODELS:
                raise ValueError(
                    "model_type must be 'random_forest' or 'logistic_regression'."
                )
            with_explanations = raw.get("with_explanations", True)
            if not isinstance(with_explanations, bool):
                raise ValueError("with_explanations must be a boolean.")
            return {
                "n_samples": sample_count,
                "n_probe": n_probe,
                "epsilon_levels": levels,
                "random_state": self._integer(raw.get("random_state", 42), "random_state"),
                "n_repeats": n_repeats,
                "model_type": model_type,
                "with_explanations": with_explanations,
            }
        if normalized_id == "EXP-CALIBRATION":
            method = raw.get("method", "sigmoid")
            if not isinstance(method, str) or method not in {"sigmoid", "isotonic"}:
                raise ValueError("method must be 'sigmoid' or 'isotonic'.")
            sample_count = self._positive_int(raw.get("n_samples", 1200), "n_samples")
            if sample_count < 400 or sample_count > 20000:
                raise ValueError("n_samples must be between 400 and 20000.")
            return {
                "n_samples": sample_count,
                "method": method,
                "random_state": self._integer(raw.get("random_state", 42), "random_state"),
            }
        if _lookup_experiment_plugin(normalized_id) is not None:
            sample_count = self._positive_int(raw.get("n_samples", 400), "n_samples")
            if sample_count < 40 or sample_count > 10000:
                raise ValueError("n_samples must be between 40 and 10000.")
            return {
                "n_samples": sample_count,
                "random_state": self._integer(raw.get("random_state", 42), "random_state"),
                "model_type": str(raw.get("model_type", "random_forest")),
            }
        raise ValueError(
            f"Unknown experiment ID '{exp_id}'. Must be one of: "
            f"{', '.join(KNOWN_EXPERIMENT_IDS)} (or a registered experiment plugin)."
        )

    @staticmethod
    def _strip_research_envelope(result: Dict[str, Any]) -> Dict[str, Any]:
        return {key: deepcopy(value) for key, value in result.items() if key not in RESEARCH_ENVELOPE_KEYS}

    def calculate_result_hash(self, result: Dict[str, Any]) -> str:
        """SHA-256 over the canonical JSON of the result with envelope keys stripped."""
        return sha256_hash(canonicalize(self._strip_research_envelope(result)))

    def calculate_configuration_hash(self, exp_id: str, config: Dict[str, Any]) -> str:
        """SHA-256 over the canonical JSON of the normalized experiment id + configuration."""
        payload = {"experiment_id": exp_id.upper().strip(), "configuration": config}
        return sha256_hash(canonicalize(payload))

    def get_git_metadata(self) -> Dict[str, Any]:
        repo_root = Path(__file__).resolve().parents[3]

        def run_git(args: List[str]) -> str:
            return subprocess.check_output(
                ["git", *args],
                cwd=repo_root,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=2,
            ).strip()

        try:
            status = run_git(["status", "--short"])
            return {
                "commit": run_git(["rev-parse", "--short", "HEAD"]),
                "branch": run_git(["rev-parse", "--abbrev-ref", "HEAD"]),
                "dirty_worktree": bool(status),
            }
        except Exception:
            return {"commit": "unknown", "branch": "unknown", "dirty_worktree": None}

    def build_run_manifest(self, result: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        exp_id = result["experiment_id"]
        reproducibility = result.get("reproducibility") or _reproducibility_metadata()
        return {
            "experiment_schema_version": EXPERIMENT_SCHEMA_VERSION,
            "experiment_id": exp_id,
            "title": result.get("title"),
            "status": result.get("status"),
            "configuration": config,
            "random_seed": config.get("random_state"),
            "result_artifact": result_artifact_name(exp_id),
            "dataset_scope": "synthetic",
            "dataset_disclaimer": SYNTHETIC_DATA_DISCLAIMER,
            "git": self.get_git_metadata(),
            "environment": {
                "python_version": reproducibility.get("python_version"),
                "platform": reproducibility.get("platform"),
                "numpy_version": reproducibility.get("numpy_version"),
                "pandas_version": reproducibility.get("pandas_version"),
                "sklearn_version": reproducibility.get("sklearn_version"),
                "shap_version": reproducibility.get("shap_version"),
            },
            "generated_at": reproducibility.get("timestamp_utc") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "plugins": result.get("plugins") or [],
        }

    @staticmethod
    def _dimension(label: str, value: Optional[float], status: str, measurement: str, explanation: str) -> Dict[str, Any]:
        return {
            "label": label,
            "value": None if value is None else round(float(value), 4),
            "status": status,
            "measurement": measurement,
            "explanation": explanation,
        }

    def build_trust_profile(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        metrics = result.get("metrics") or {}
        comparison = result.get("comparison") or {}

        detection_value: Optional[float] = None
        detection_measurement = "No detection metric available for this experiment."
        if "in_distribution" in metrics:
            detection_value = metrics["in_distribution"].get("f1_score")
            detection_measurement = "In-distribution F1 score from EXP-A."
        elif "random_forest" in comparison:
            detection_value = comparison["random_forest"].get("f1_score")
            detection_measurement = "Random Forest F1 score from EXP-D."
        elif "overall_mean_stability" in metrics:
            detection_measurement = "EXP-B measures explanation stability, not detection quality."
        elif "clean_chain_valid" in metrics:
            detection_measurement = "EXP-C measures ledger integrity, not detection quality."

        stability_value = metrics.get("overall_mean_stability")
        evidence_value = None
        if "clean_chain_valid" in metrics:
            rate_text = str(metrics.get("tamper_detection_rate", "0%")).replace("%", "")
            try:
                evidence_value = float(rate_text) / 100.0 if metrics.get("clean_chain_valid") else 0.0
            except ValueError:
                evidence_value = 0.0

        manifest_ready = bool(result.get("reproducibility")) and bool(result.get("parameters") or comparison)
        reproducibility_value = 1.0 if manifest_ready else 0.75

        return [
            self._dimension("Detection", detection_value, "measured" if detection_value is not None else "not_applicable", detection_measurement, "Detection trust is derived only from available F1 metrics."),
            self._dimension("Explanation Stability", stability_value, "measured" if stability_value is not None else "not_applicable", "Mean cosine SHAP stability from EXP-B when available.", "Explanation stability is measured only for the XAI perturbation experiment."),
            self._dimension("Evidence Integrity", evidence_value, "measured" if evidence_value is not None else "not_applicable", "Clean-chain verification and tamper detection rate from EXP-C when available.", "Evidence integrity uses controlled synthetic ledger tampering, not a production guarantee."),
            self._dimension("Reproducibility", reproducibility_value, "measured", "Manifest completeness, deterministic configuration, environment metadata, and canonical hashes.", "Reproducibility reflects whether the run records enough metadata to rerun and inspect the experiment."),
            self._dimension("Data Quality", None, "not_evaluated", "No real dataset health report is attached to this synthetic benchmark.", "No real dataset health report exists for this run, so data quality is not scored."),
        ]

    def enrich_research_result(self, result: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Attach the research envelope: run manifest, canonical hashes, trust profile, evidence state."""
        enriched = deepcopy(result)
        exp_id = enriched["experiment_id"]
        normalized_config = self.validate_experiment_config(exp_id, config or enriched.get("parameters") or {})
        enriched["run_manifest"] = self.build_run_manifest(enriched, normalized_config)
        enriched["result_hash"] = self.calculate_result_hash(enriched)
        enriched["configuration_hash"] = self.calculate_configuration_hash(exp_id, normalized_config)
        enriched["trust_profile"] = self.build_trust_profile(enriched)
        enriched["evidence_package"] = {"status": "not_exported"}
        return enriched

    def export_evidence_package(self, exp_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        normalized_id = exp_id.upper().strip()
        if result_artifact_name(normalized_id) is None:
            raise ValueError(
                f"Unknown experiment ID '{exp_id}'. Must be a core experiment or a registered plugin."
            )

        result = self.run_experiment_by_id(normalized_id, config=config) if config else self.get_experiment_by_id(normalized_id)
        if result is None:
            result = self.run_experiment_by_id(normalized_id, config=config)

        package_dir = RESULTS_DIR / "evidence" / normalized_id
        package_dir.mkdir(parents=True, exist_ok=True)

        metrics_payload = result.get("metrics") or result.get("comparison") or {}
        verification_report = {
            **version_metadata(),
            "experiment_id": normalized_id,
            "status": result.get("status"),
            "result_hash": result.get("result_hash"),
            "configuration_hash": result.get("configuration_hash"),
            "trust_profile": result.get("trust_profile", []),
            "ledger_scope": "synthetic_controlled_demo" if normalized_id == "EXP-C" else "not_applicable",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        package_manifest = {
            **version_metadata(),
            "experiment_id": normalized_id,
        }
        files_to_write = {
            "package-manifest.json": package_manifest,
            "experiment.json": result,
            "metrics.json": metrics_payload,
            "reproducibility-manifest.json": result.get("run_manifest", {}),
            "verification-report.json": verification_report,
        }

        for filename, payload in files_to_write.items():
            with open(package_dir / filename, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=True)

        readme = (
            f"# SentinelCrypt Evidence Package: {normalized_id}\n\n"
            f"Generated: {verification_report['generated_at']}\n\n"
            "This package contains deterministic research evidence exported from SentinelCrypt AI.\n"
            "Current benchmark experiments use synthetic data unless a manifest states otherwise.\n"
        )
        with open(package_dir / "README.md", "w", encoding="utf-8") as f:
            f.write(readme)

        file_hashes = {}
        for file_path in sorted(package_dir.iterdir(), key=lambda p: p.name):
            if file_path.is_file():
                file_hashes[file_path.name] = hash_file(str(file_path))
        with open(package_dir / "file-hashes.json", "w", encoding="utf-8") as f:
            json.dump(file_hashes, f, indent=2, sort_keys=True)
        file_hashes["file-hashes.json"] = hash_file(str(package_dir / "file-hashes.json"))

        package_hash = sha256_hash(canonicalize({"files": file_hashes}))
        files = sorted(file_hashes.keys())

        response = {
            **version_metadata(),
            "experiment_id": normalized_id,
            "package_path": str(package_dir.as_posix()),
            "files": files,
            "file_hashes": file_hashes,
            "package_hash": package_hash,
            "generated_at": verification_report["generated_at"],
        }
        if self.db is not None:
            from backend.app.services.lineage_service import (
                ArtifactLineageService,
                artifact_digest,
            )

            result_payload = {
                "experiment_id": normalized_id,
                "result_hash": result.get("result_hash"),
                "configuration_hash": result.get("configuration_hash"),
            }
            experiment_artifact_id = (
                f"research-experiment:{normalized_id}:{artifact_digest(result_payload)[:12]}"
            )
            result_artifact_id = (
                f"research-results:{normalized_id}:{artifact_digest(metrics_payload)[:12]}"
            )
            report_digest = artifact_digest(verification_report)
            report_artifact_id = f"verification-report:{normalized_id}:{report_digest[:12]}"
            package_artifact_id = f"evidence-package:{normalized_id}:{package_hash[:12]}"
            ArtifactLineageService(self.db).record_chain([
                {
                    "artifact_id": experiment_artifact_id,
                    "artifact_type": "experiment",
                    "version": str(EXPERIMENT_SCHEMA_VERSION),
                    "sha256": artifact_digest(result_payload),
                    "experiment_id": normalized_id,
                    "metadata": {
                        **result_payload,
                        "digest_scope": "canonical stored experiment identity and hashes",
                    },
                },
                {
                    "artifact_id": result_artifact_id,
                    "artifact_type": "results",
                    "parent_artifact_id": experiment_artifact_id,
                    "version": str(EXPERIMENT_SCHEMA_VERSION),
                    "sha256": artifact_digest(metrics_payload),
                    "experiment_id": normalized_id,
                    "metadata": {
                        "result_hash": result.get("result_hash"),
                        "digest_scope": "canonical experiment metrics/comparison payload",
                    },
                },
                {
                    "artifact_id": report_artifact_id,
                    "artifact_type": "report",
                    "parent_artifact_id": result_artifact_id,
                    "version": str(EXPERIMENT_SCHEMA_VERSION),
                    "sha256": report_digest,
                    "experiment_id": normalized_id,
                    "metadata": {
                        "file_name": "verification-report.json",
                        "digest_scope": "canonical verification report before package export",
                    },
                },
                {
                    "artifact_id": package_artifact_id,
                    "artifact_type": "evidence_package",
                    "parent_artifact_id": report_artifact_id,
                    "version": str(EXPERIMENT_SCHEMA_VERSION),
                    "sha256": package_hash,
                    "experiment_id": normalized_id,
                    "metadata": {
                        "experiment_id": normalized_id,
                        "files": files,
                        "digest_scope": "SHA-256 over the exported package file inventory",
                    },
                },
            ])
        result["evidence_package"] = {
            "status": "exported",
            "package_path": response["package_path"],
            "package_hash": package_hash,
            "generated_at": response["generated_at"],
        }
        return response

    @staticmethod
    def _experiment_highlight(exp: Dict[str, Any]) -> Dict[str, Any]:
        exp_id = exp.get("experiment_id")
        if exp.get("status") != "COMPLETED":
            return {"experiment_id": exp_id, "status": exp.get("status"), "highlight": "Ready to run"}

        metrics = exp.get("metrics") or {}
        comparison = exp.get("comparison") or {}

        if exp_id == "EXP-A":
            in_f1 = metrics.get("in_distribution", {}).get("f1_score")
            out_f1 = metrics.get("out_of_distribution", {}).get("f1_score")
            return {"experiment_id": exp_id, "status": "COMPLETED", "highlight": f"In-distribution F1 {in_f1}; out-of-distribution F1 {out_f1}"}
        if exp_id == "EXP-B":
            stability = metrics.get("overall_mean_stability")
            return {"experiment_id": exp_id, "status": "COMPLETED", "highlight": f"Mean SHAP stability {stability}"}
        if exp_id == "EXP-C":
            detection = metrics.get("tamper_detection_rate")
            return {"experiment_id": exp_id, "status": "COMPLETED", "highlight": f"Tamper detection rate {detection}"}
        if exp_id == "EXP-F":
            deltas = metrics.get("deltas_vs_full", {})
            parts = [f"{k}: ΔF1 {v.get('f1', 0):+.4f}" for k, v in deltas.items()]
            return {"experiment_id": exp_id, "status": "COMPLETED",
                    "highlight": "; ".join(parts) or "No ablation deltas available"}
        if exp_id == "EXP-G":
            tamper = metrics.get("tamper_detection", {})
            return {"experiment_id": exp_id, "status": "COMPLETED",
                    "highlight": f"Mutation detected: {tamper.get('mutation_all_sizes')}; "
                                 f"Omission detected: {tamper.get('omission_all_sizes')}"}
        if exp_id == "EXP-H":
            clean = metrics.get("clean_agreement", {})
            return {"experiment_id": exp_id, "status": "COMPLETED",
                    "highlight": f"Mean top-k overlap {clean.get('mean_topk_overlap')}; "
                                 f"mean Spearman {clean.get('mean_spearman')}"}
        if exp_id == "EXP-D":
            rf_f1 = comparison.get("random_forest", {}).get("f1_score")
            lr_f1 = comparison.get("logistic_regression", {}).get("f1_score")
            return {"experiment_id": exp_id, "status": "COMPLETED", "highlight": f"Random Forest F1 {rf_f1}; Logistic Regression F1 {lr_f1}"}
        return {"experiment_id": exp_id, "status": exp.get("status"), "highlight": "No highlight available"}

    def build_presentation_summary(self) -> Dict[str, Any]:
        experiments = self.list_experiments()
        completed = [exp for exp in experiments if exp.get("status") == "COMPLETED"]

        return {
            "research_question": "How does explanation reliability and cryptographic evidence verification affect the trustworthiness of machine-learning-based network intrusion detection?",
            "methodology": [
                "Validate or generate deterministic network-flow data.",
                "Train leakage-conscious baseline and ensemble ML models.",
                "Evaluate detection metrics and runtime trade-offs.",
                "Generate SHAP explanations and perturbation-based stability measurements.",
                "Canonicalize evidence and anchor records in a SHA-256 forward-linked audit ledger.",
                "Export reproducibility metadata, hashes, and evidence packages for inspection.",
            ],
            "datasets": [
                {"name": "Synthetic SentinelCrypt Flow Benchmark", "status": "implemented", "scope": "Current EXP-A through EXP-D benchmark data."},
                {"name": "UNSW-NB15", "status": "planned", "scope": "Real dataset support requires feature mapping and checksum validation."},
                {"name": "CICIDS2017", "status": "planned", "scope": "Real cross-dataset evaluation requires compatible feature representation."},
            ],
            "models": ["Logistic Regression", "Random Forest"],
            "xai_method": "SHAP explanations with perturbation-based stability analysis.",
            "cryptographic_evidence": "RFC 8785-style canonical JSON, SHA-256 payload hashes, and a forward-linked tamper-evident audit ledger.",
            "experiments": [self._experiment_highlight(exp) for exp in experiments],
            "completed_experiments": len(completed),
            "total_experiments": len(experiments),
            "limitations": [
                "Current experiments use synthetic data.",
                "The audit ledger is tamper-evident, not tamper-proof.",
                "SentinelCrypt AI is a research prototype, not a production IDS.",
            ],
            "future_work": [
                "Register real UNSW-NB15/CICIDS2017 captures to replace synthetic proxies.",
                "Independent multi-lab reproduction of the benchmark protocol.",
            ],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # EXP-A: Cross-Dataset Generalization
    # ─────────────────────────────────────────────────────────────────────────

    def run_exp_a(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute EXP-A: Quantifies in-domain vs out-of-domain Generalization Gap.

        Uses synthetic data partitions with controlled distribution shift.
        The source partition uses shift_scale=1.0 and the target uses shift_scale=1.65
        with different attack ratios to simulate distribution shift.

        NOTE: This does NOT use real UNSW-NB15 or CICIDS2017 datasets.
        Cross-dataset evaluation on real datasets is planned future work.
        """
        cfg = config or {}
        n_samples = cfg.get("n_samples", 1200)
        random_state = cfg.get("random_state", 42)

        source_df = self.generate_synthetic_flow_dataset(
            n_samples=n_samples, random_state=random_state, shift_scale=1.0
        )
        target_df = self.generate_synthetic_flow_dataset(
            n_samples=n_samples, random_state=random_state + 10, shift_scale=1.65, attack_ratio=0.35
        )

        features = [c for c in source_df.columns if c != "label"]
        X_src = source_df[features]
        y_src = source_df["label"]
        X_tgt = target_df[features]
        y_tgt = target_df["label"]

        X_src_train, X_src_test, y_src_train, y_src_test = train_test_split(
            X_src, y_src, test_size=0.3, random_state=random_state, stratify=y_src
        )

        model = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=random_state)
        model.fit(X_src_train, y_src_train)

        # In-Domain
        src_preds = model.predict(X_src_test)
        src_probs = model.predict_proba(X_src_test)[:, 1]
        src_f1 = float(f1_score(y_src_test, src_preds, zero_division=0))
        src_acc = float(accuracy_score(y_src_test, src_preds))
        src_prec = float(precision_score(y_src_test, src_preds, zero_division=0))
        src_rec = float(recall_score(y_src_test, src_preds, zero_division=0))
        src_auc = float(roc_auc_score(y_src_test, src_probs))

        # Out-of-Domain
        tgt_preds = model.predict(X_tgt)
        tgt_probs = model.predict_proba(X_tgt)[:, 1]
        tgt_f1 = float(f1_score(y_tgt, tgt_preds, zero_division=0))
        tgt_acc = float(accuracy_score(y_tgt, tgt_preds))
        tgt_prec = float(precision_score(y_tgt, tgt_preds, zero_division=0))
        tgt_rec = float(recall_score(y_tgt, tgt_preds, zero_division=0))
        tgt_auc = float(roc_auc_score(y_tgt, tgt_probs))

        gen_gap_f1 = round(src_f1 - tgt_f1, 4)
        gen_gap_acc = round(src_acc - tgt_acc, 4)

        result = {
            "experiment_id": "EXP-A",
            "title": "Cross-Dataset Generalization Gap (Synthetic Data)",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "COMPLETED",
            "reproducibility": _reproducibility_metadata(),
            "parameters": {
                "n_samples": n_samples,
                "model": "RandomForestClassifier",
                "random_state": random_state,
                "source_shift_scale": 1.0,
                "target_shift_scale": 1.65,
                "source_attack_ratio": 0.3,
                "target_attack_ratio": 0.35,
                "features": features,
                "note": "Synthetic data partitions with controlled distribution shift. Not real UNSW-NB15/CICIDS2017 datasets.",
            },
            "metrics": {
                "in_distribution": {
                    "dataset": "Source Synthetic Partition (shift_scale=1.0)",
                    "accuracy": round(src_acc, 4),
                    "f1_score": round(src_f1, 4),
                    "precision": round(src_prec, 4),
                    "recall": round(src_rec, 4),
                    "roc_auc": round(src_auc, 4),
                },
                "out_of_distribution": {
                    "dataset": "Target Synthetic Partition (shift_scale=1.65)",
                    "accuracy": round(tgt_acc, 4),
                    "f1_score": round(tgt_f1, 4),
                    "precision": round(tgt_prec, 4),
                    "recall": round(tgt_rec, 4),
                    "roc_auc": round(tgt_auc, 4),
                },
                "generalization_gap": {
                    "delta_f1": gen_gap_f1,
                    "delta_accuracy": gen_gap_acc,
                    "interpretation": (
                        f"A performance drop of {gen_gap_f1*100:.1f}% F1 was observed due to "
                        "distribution shift across independent network environments."
                    ),
                },
            },
        }

        result = self.enrich_research_result(result, cfg)

        out_file = RESULTS_DIR / "exp_a_cross_dataset.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # EXP-B: XAI Explanation Stability under Perturbation
    # ─────────────────────────────────────────────────────────────────────────

    def run_exp_b(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute EXP-B: Evaluates SHAP attribution stability across Gaussian noise levels."""
        cfg = config or {}
        random_state = cfg.get("random_state", 42)
        noise_levels = cfg.get("noise_levels", [0.01, 0.05, 0.10, 0.20])
        n_repetitions = cfg.get("n_repetitions", 8)

        df = self.generate_synthetic_flow_dataset(n_samples=500, random_state=random_state)
        features = [c for c in df.columns if c != "label"]
        X = df[features].values
        y = df["label"].values

        detector = RandomForestDetector(
            hyperparameters={"n_estimators": 30, "max_depth": 6},
            random_seed=random_state,
        )
        detector.fit(X, y, feature_names=features)

        explainer = SHAPExplainer(
            detector=detector,
            X_background=X[:100],
            feature_names=features,
        )

        stability_curve = []
        test_sample = X[y == 1][0:1]  # Shape (1, n_features)

        for sigma in noise_levels:
            analyzer = ExplanationStabilityAnalyzer(
                explainer=explainer,
                n_repetitions=n_repetitions,
                noise_std=sigma,
                random_seed=random_state,
            )
            report = analyzer.analyze(test_sample)
            stability_curve.append({
                "noise_std": sigma,
                "stability_score": round(report.stability_score, 4),
                "std": round(report.std, 4),
            })

        mean_stability = float(np.mean([s["stability_score"] for s in stability_curve]))

        result = {
            "experiment_id": "EXP-B",
            "title": "XAI Explanation Stability under Input Perturbation",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "COMPLETED",
            "reproducibility": _reproducibility_metadata(),
            "parameters": {
                "model_type": "TreeSHAP (RandomForest)",
                "noise_std_levels": noise_levels,
                "n_repetitions": n_repetitions,
                "random_state": random_state,
            },
            "metrics": {
                "overall_mean_stability": round(mean_stability, 4),
                "stability_curve": stability_curve,
                "interpretation": (
                    "SHAP attributions demonstrated high stability "
                    f"(mean cosine similarity = {mean_stability:.3f}) under sensor noise."
                ),
            },
        }

        result = self.enrich_research_result(result, cfg)

        out_file = RESULTS_DIR / "exp_b_xai_stability.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # EXP-C: Cryptographic Audit Ledger Integrity & Adversarial Attacks
    # ─────────────────────────────────────────────────────────────────────────

    def run_exp_c(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute EXP-C: Simulates adversarial ledger tamper attacks and evaluates verifier detection."""
        cfg = config or {}
        n_blocks = cfg.get("n_blocks", 50)
        random_state = cfg.get("random_state", 42)
        rng = np.random.RandomState(random_state)

        # 1. Build a clean in-memory hash chain
        records: List[SimpleNamespace] = []
        prev_hash = GENESIS_PREVIOUS_HASH

        start_time = time.perf_counter()
        for i in range(1, n_blocks + 1):
            payload = {
                "sequence_number": i,
                "timestamp": f"2026-09-21T12:00:{i:02d}Z",
                "model_id": "model-sentinel-01",
                "predicted_class": int(rng.choice([0, 1])),
                "probability": round(float(rng.uniform(0.6, 0.99)), 4),
                "features": {"dur": float(rng.exponential(0.1)), "rate": float(rng.uniform(100, 5000))},
            }
            can_json, p_hash, r_hash = build_audit_record_hashes(payload, prev_hash)
            records.append(SimpleNamespace(
                sequence_number=i,
                payload_json=can_json,
                previous_hash=prev_hash,
                record_hash=r_hash,
                payload=payload,
            ))
            prev_hash = r_hash

        build_latency_ms = (time.perf_counter() - start_time) * 1000

        # 2. Test Clean Chain Verification
        clean_res = verify_ledger(records)

        # 3. Simulate Attack 1: Payload Bit-Flip / Mutation
        tamper_idx_1 = max(1, n_blocks // 4)
        records_tampered_payload = []
        for r in records:
            if r.sequence_number == tamper_idx_1:
                tampered_p = dict(r.payload)
                tampered_p["probability"] = 0.999999
                records_tampered_payload.append(SimpleNamespace(
                    sequence_number=r.sequence_number,
                    payload_json=json.dumps(tampered_p),
                    previous_hash=r.previous_hash,
                    record_hash=r.record_hash,
                    payload=tampered_p,
                ))
            else:
                records_tampered_payload.append(r)
        res_attack_1 = verify_ledger(records_tampered_payload)

        # 4. Simulate Attack 2: Previous-Hash Pointer Rewrite
        tamper_idx_2 = max(2, n_blocks // 2)
        records_tampered_pointer = []
        for r in records:
            if r.sequence_number == tamper_idx_2:
                records_tampered_pointer.append(SimpleNamespace(
                    sequence_number=r.sequence_number,
                    payload_json=r.payload_json,
                    previous_hash="deadbeef" * 8,
                    record_hash=r.record_hash,
                    payload=r.payload,
                ))
            else:
                records_tampered_pointer.append(r)
        res_attack_2 = verify_ledger(records_tampered_pointer)

        # 5. Simulate Attack 3: Intermediate Block Deletion (Sequence Drop)
        tamper_idx_3 = max(3, (3 * n_blocks) // 4)
        records_deleted = [r for r in records if r.sequence_number != tamper_idx_3]
        res_attack_3 = verify_ledger(records_deleted)

        attacks_evaluated = [
            {
                "attack_type": "Payload Mutation (Feature/Probability Bit-Flip)",
                "tampered_sequence": tamper_idx_1,
                "detected": not res_attack_1.verified,
                "detected_at_sequence": res_attack_1.failed_records[0]["sequence_number"] if res_attack_1.failed_records else None,
                "status": "PASSED" if not res_attack_1.verified and res_attack_1.failed_records and res_attack_1.failed_records[0]["sequence_number"] == tamper_idx_1 else "FAILED",
            },
            {
                "attack_type": "Previous-Hash Pointer Modification",
                "tampered_sequence": tamper_idx_2,
                "detected": not res_attack_2.verified,
                "detected_at_sequence": res_attack_2.failed_records[0]["sequence_number"] if res_attack_2.failed_records else None,
                "status": "PASSED" if not res_attack_2.verified and res_attack_2.failed_records and res_attack_2.failed_records[0]["sequence_number"] == tamper_idx_2 else "FAILED",
            },
            {
                "attack_type": "Block Omission (Sequence Deletion)",
                "tampered_sequence": tamper_idx_3,
                "detected": not res_attack_3.verified,
                "detected_at_sequence": res_attack_3.failed_records[0]["sequence_number"] if res_attack_3.failed_records else None,
                "status": "PASSED" if not res_attack_3.verified else "FAILED",
            },
        ]

        detection_rate = 100.0 if all(a["detected"] for a in attacks_evaluated) else 0.0

        result = {
            "experiment_id": "EXP-C",
            "title": "Cryptographic Audit Integrity & Adversarial Tamper Attacks (Synthetic Benchmarks)",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "COMPLETED",
            "reproducibility": _reproducibility_metadata(),
            "parameters": {
                "n_blocks_evaluated": n_blocks,
                "hash_algorithm": "SHA-256 (Canonical RFC 8785)",
            },
            "metrics": {
                "clean_chain_valid": clean_res.verified,
                "tamper_detection_rate": f"{detection_rate}%",
                "attacks_simulated": attacks_evaluated,
                "throughput": {
                    "total_chain_build_ms": round(build_latency_ms, 2),
                    "mean_append_time_us": round((build_latency_ms / n_blocks) * 1000, 2),
                    "mean_verification_time_us": round((clean_res.duration_ms / n_blocks) * 1000, 2),
                },
            },
        }

        result = self.enrich_research_result(result, cfg)

        out_file = RESULTS_DIR / "exp_c_ledger_integrity.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # EXP-D: Model Architecture & Runtime Overhead Comparison
    # ─────────────────────────────────────────────────────────────────────────

    def run_exp_d(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute EXP-D: Direct comparison of Logistic Regression vs Random Forest on metrics & latency."""
        cfg = config or {}
        n_samples = cfg.get("n_samples", 1500)
        random_state = cfg.get("random_state", 42)

        df = self.generate_synthetic_flow_dataset(n_samples=n_samples, random_state=random_state)
        features = [c for c in df.columns if c != "label"]
        X = df[features].values
        y = df["label"].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=random_state, stratify=y
        )

        # Model 1: Logistic Regression
        lr = LogisticRegression(max_iter=500, random_state=random_state)
        t0 = time.perf_counter()
        lr.fit(X_train, y_train)
        lr_train_time_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        lr_preds = lr.predict(X_test)
        lr_probs = lr.predict_proba(X_test)[:, 1]
        lr_infer_us_per_sample = ((time.perf_counter() - t0) / len(X_test)) * 1_000_000

        lr_f1 = float(f1_score(y_test, lr_preds, zero_division=0))
        lr_acc = float(accuracy_score(y_test, lr_preds))
        lr_auc = float(roc_auc_score(y_test, lr_probs))

        # Model 2: Random Forest
        rf = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=random_state)
        t0 = time.perf_counter()
        rf.fit(X_train, y_train)
        rf_train_time_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        rf_preds = rf.predict(X_test)
        rf_probs = rf.predict_proba(X_test)[:, 1]
        rf_infer_us_per_sample = ((time.perf_counter() - t0) / len(X_test)) * 1_000_000

        rf_f1 = float(f1_score(y_test, rf_preds, zero_division=0))
        rf_acc = float(accuracy_score(y_test, rf_preds))
        rf_auc = float(roc_auc_score(y_test, rf_probs))

        # Measure Cryptographic Overhead (Canonical JSON + SHA-256)
        sample_payload = {
            "model_id": "rf-01",
            "features": {f: float(X_test[0][i]) for i, f in enumerate(features)},
            "predicted_class": 1,
            "probability": 0.985,
        }
        t0 = time.perf_counter()
        for _ in range(500):
            can_bytes = canonicalize(sample_payload)
            h = sha256_hash(can_bytes)
        crypto_overhead_us = ((time.perf_counter() - t0) / 500) * 1_000_000

        result = {
            "experiment_id": "EXP-D",
            "title": "Model Architecture & Runtime Overhead Comparison",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "COMPLETED",
            "reproducibility": _reproducibility_metadata(),
            "comparison": {
                "logistic_regression": {
                    "model_type": "Logistic Regression (Linear Baseline)",
                    "accuracy": round(lr_acc, 4),
                    "f1_score": round(lr_f1, 4),
                    "roc_auc": round(lr_auc, 4),
                    "training_time_ms": round(lr_train_time_ms, 2),
                    "inference_time_us": round(lr_infer_us_per_sample, 2),
                },
                "random_forest": {
                    "model_type": "Random Forest (Non-linear Ensemble)",
                    "accuracy": round(rf_acc, 4),
                    "f1_score": round(rf_f1, 4),
                    "roc_auc": round(rf_auc, 4),
                    "training_time_ms": round(rf_train_time_ms, 2),
                    "inference_time_us": round(rf_infer_us_per_sample, 2),
                },
                "cryptographic_overhead": {
                    "canonicalization_and_sha256_us": round(crypto_overhead_us, 2),
                    "relative_overhead_pct": f"~{((crypto_overhead_us / (rf_infer_us_per_sample + crypto_overhead_us)) * 100):.1f}% of total pipeline",
                },
            },
        }

        result = self.enrich_research_result(result, cfg)

        out_file = RESULTS_DIR / "exp_d_model_comparison.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # List & Retrieve Experiment Results
    # ─────────────────────────────────────────────────────────────────────────

    def list_experiments(self) -> List[Dict[str, Any]]:
        """List summary status of all registered research experiments."""
        results = []
        for meta in EXPERIMENT_META:
            file_path = RESULTS_DIR / EXPERIMENT_RESULT_FILES[meta["id"]]
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    results.append(data)
                    continue
                except Exception:
                    pass
            results.append({
                "experiment_id": meta["id"],
                "title": meta["title"],
                "status": "READY_TO_RUN",
                "metrics": None,
            })
        for item in _list_experiment_plugins():
            exp_id = str(item.get("metadata", {}).get("experiment_id") or item["name"]).upper()
            if any(row.get("experiment_id") == exp_id for row in results):
                continue
            filename = result_artifact_name(exp_id)
            file_path = RESULTS_DIR / filename if filename else None
            if file_path is not None and file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as handle:
                        results.append(json.load(handle))
                        continue
                except Exception:
                    pass
            results.append({
                "experiment_id": exp_id,
                "title": item.get("description") or exp_id,
                "status": "READY_TO_RUN",
                "metrics": None,
                "plugin": item["name"],
            })
        return results

    def get_experiment_by_id(self, exp_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve stored experiment details or run if not yet executed."""
        normalized_id = exp_id.upper().strip()
        filename = result_artifact_name(normalized_id)
        if not filename:
            return None

        file_path = RESULTS_DIR / filename
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "run_manifest" not in data:
                    return self.enrich_research_result(data, data.get("parameters") or {})
                return data
            except Exception:
                pass

        return self.run_experiment_by_id(normalized_id)

    def run_experiment_by_id(self, exp_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Trigger execution of specified experiment."""
        normalized_id = exp_id.upper().strip()
        runners = {
            "EXP-A": self.run_exp_a,
            "EXP-B": self.run_exp_b,
            "EXP-C": self.run_exp_c,
            "EXP-D": self.run_exp_d,
            "EXP-F": self.run_exp_f,
            "EXP-G": self.run_exp_g,
            "EXP-H": self.run_exp_h,
            "EXP-ROBUSTNESS": self.run_exp_robustness,
            "EXP-CALIBRATION": self.run_exp_calibration,
        }
        runner = runners.get(normalized_id)
        if runner is not None:
            return runner(config)
        plugin = _lookup_experiment_plugin(normalized_id)
        if plugin is None:
            raise ValueError(
                f"Unknown experiment ID '{exp_id}'. Must be one of: "
                f"{', '.join(KNOWN_EXPERIMENT_IDS)} (or a registered experiment plugin)."
            )
        from backend.app.plugins.host import PluginHost

        return PluginHost().run_experiment(self, plugin.name, config)

    # ─────────────────────────────────────────────────────────────────────────
    # EXP-F: Component Ablation Study
    # ─────────────────────────────────────────────────────────────────────────

    def run_exp_f(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute EXP-F: which pipeline components contribute what (item: ablation)."""
        from backend.app.research.ablation import run_ablation

        cfg = self.validate_experiment_config("EXP-F", config or {})
        result = run_ablation(
            n_samples=cfg.get("n_samples", 1200),
            seed=cfg.get("random_state", 42),
            variants=cfg.get("variants"),
            model_type=cfg.get("model_type", "random_forest"),
            repeats=cfg.get("repeats", 3),
            explanation_samples=cfg.get("explanation_samples", 1),
        )
        result = self.enrich_research_result(result, cfg)
        out_file = RESULTS_DIR / EXPERIMENT_RESULT_FILES["EXP-F"]
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # EXP-G: Hash Chain vs Merkle Integrity Architecture Comparison
    # ─────────────────────────────────────────────────────────────────────────

    def run_exp_g(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute EXP-G: measured head-to-head of hash chain vs Merkle tree."""
        from backend.app.research.integrity_comparison import run_integrity_comparison

        cfg = config or {}
        result = run_integrity_comparison(
            sizes=cfg.get("sizes"),
            seed=cfg.get("random_state", 42),
        )
        result = self.enrich_research_result(result, cfg)
        out_file = RESULTS_DIR / EXPERIMENT_RESULT_FILES["EXP-G"]
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # EXP-H: Cross-Method Explanation Agreement
    # ─────────────────────────────────────────────────────────────────────────

    def run_exp_h(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute EXP-H: SHAP vs permutation vs built-in importance agreement."""
        from backend.app.research.xai_agreement_study import run_xai_agreement

        cfg = config or {}
        result = run_xai_agreement(
            n_samples=cfg.get("n_samples", 800),
            top_k=cfg.get("top_k", 5),
            seed=cfg.get("random_state", 42),
            noise_levels=cfg.get("noise_levels"),
            model_type=cfg.get("model_type", "random_forest"),
        )
        result = self.enrich_research_result(result, cfg)
        out_file = RESULTS_DIR / EXPERIMENT_RESULT_FILES["EXP-H"]
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # EXP-ROBUSTNESS: Offline bounded-perturbation sensitivity measurements
    # ─────────────────────────────────────────────────────────────────────────

    def run_exp_robustness(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run the offline synthetic-feature sensitivity experiment."""
        from backend.app.research.robustness import run_robustness_study

        cfg = self.validate_experiment_config("EXP-ROBUSTNESS", config or {})
        result = run_robustness_study(
            n_samples=cfg["n_samples"],
            n_probe=cfg["n_probe"],
            epsilon_levels=cfg["epsilon_levels"],
            seed=cfg["random_state"],
            with_explanations=cfg["with_explanations"],
            n_repeats=cfg["n_repeats"],
            model_type=cfg["model_type"],
            experiment_id="EXP-ROBUSTNESS",
        )
        result = self.enrich_research_result(result, cfg)
        out_file = RESULTS_DIR / EXPERIMENT_RESULT_FILES["EXP-ROBUSTNESS"]
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        return result

    def run_exp_calibration(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run a synthetic calibration study using disjoint data partitions."""
        from backend.app.research.calibration_lab import run_calibration_study

        cfg = self.validate_experiment_config("EXP-CALIBRATION", config or {})
        result = run_calibration_study(
            n_samples=cfg["n_samples"],
            method=cfg["method"],
            seed=cfg["random_state"],
        )
        result = self.enrich_research_result(result, cfg)
        out_file = RESULTS_DIR / EXPERIMENT_RESULT_FILES["EXP-CALIBRATION"]
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        return result
