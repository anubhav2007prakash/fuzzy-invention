"""Paired measurements of SentinelCrypt's ML, XAI, and evidence components."""
from __future__ import annotations

import json
import hashlib
import os
import pickle
import statistics
import time
from datetime import datetime, timezone
import tracemalloc
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    build_audit_record_hashes,
)
from backend.app.cryptography.hashing import sha256_hash
from backend.app.cryptography.verifier import verify_ledger
from backend.app.ml.data.synthetic import generate_flow_dataset
from backend.app.ml.evaluation.research_metrics import (
    classification_metrics,
)
from backend.app.ml.evaluation.statistical_analysis import (
    bootstrap_trial_summary,
    paired_bootstrap_comparison,
)
from backend.app.ml.preprocessing.validators import validate_dataset
from backend.app.xai.shap_explainer import SHAPExplainer

ARMS: dict[str, dict[str, Any]] = {
    "A": {
        "name": "ML only",
        "xai": False,
        "evidence": False,
        "full_provenance": False,
    },
    "B": {
        "name": "ML + XAI",
        "xai": True,
        "evidence": False,
        "full_provenance": False,
    },
    "C": {
        "name": "ML + cryptographic evidence",
        "xai": False,
        "evidence": True,
        "full_provenance": False,
    },
    "D": {
        "name": "ML + XAI + cryptographic evidence",
        "xai": True,
        "evidence": True,
        "full_provenance": False,
    },
    "E": {
        "name": "Full SentinelCrypt",
        "xai": True,
        "evidence": True,
        "full_provenance": True,
    },
}

# Backward-compatible aliases for existing callers and saved experiment configs.
_LEGACY_ARMS = {
    "full": "E",
    "no_xai": "C",
    "no_evidence": "B",
}
VARIANTS = (*ARMS, *_LEGACY_ARMS)


class _Probe:
    def __init__(self, model: Any):
        self.raw_model = model
        self.model_type = (
            "random_forest"
            if hasattr(model, "feature_importances_")
            else "logistic_regression"
        )
        self.classes_ = getattr(model, "classes_", None)

    def predict(self, features: np.ndarray) -> np.ndarray:
        return self.raw_model.predict(features)

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        return self.raw_model.predict_proba(features)


def _mean(values: list[float | int | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return round(statistics.fmean(present), 6) if present else None


def _memory_peak_mb(function: Any) -> tuple[Any, float]:
    tracing_before = tracemalloc.is_tracing()
    if tracing_before:
        current_before, _ = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
    else:
        current_before = 0
        tracemalloc.start()
    try:
        result = function()
        _, peak_bytes = tracemalloc.get_traced_memory()
        return result, round(max(0, peak_bytes - current_before) / (1024 * 1024), 6)
    finally:
        if not tracing_before:
            tracemalloc.stop()


def _model(model_type: str, seed: int) -> Any:
    if model_type == "logistic_regression":
        return LogisticRegression(max_iter=500, random_state=seed)
    if model_type == "random_forest":
        return RandomForestClassifier(n_estimators=50, max_depth=8, random_state=seed)
    raise ValueError("model_type must be 'random_forest' or 'logistic_regression'.")


def _prediction_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_probability: np.ndarray,
) -> dict[str, float]:
    return classification_metrics(y_true, y_pred, y_probability)


def _measure_evidence(
    *,
    y_pred: np.ndarray,
    y_probability: np.ndarray,
    model_type: str,
    run_id: str,
    top_features: list[dict[str, Any]] | None,
    full_provenance: bool,
    lineage_artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    records = []
    total_generation_ms = 0.0
    evidence_bytes = 0
    lineage_bytes = 0
    previous_hash = GENESIS_PREVIOUS_HASH

    for index, (prediction, probability) in enumerate(zip(y_pred, y_probability)):
        started = time.perf_counter()
        event = {
            "event_type": "ABLATION_PREDICTION",
            "run_id": run_id,
            "sample_index": index,
            "model_type": model_type,
            "predicted_class": int(prediction),
            "positive_class_probability": float(probability),
        }
        if top_features is not None and index == 0:
            event["explanation"] = top_features
        if full_provenance:
            event["protocol_version"] = "1"
            event["schema_version"] = "1"
            event["provenance"] = {
                "run_id": run_id,
                "parent": f"model:{run_id}",
                "artifact_type": "prediction",
            }

        canonical_payload, _, record_hash = build_audit_record_hashes(
            event, previous_hash
        )
        record = SimpleNamespace(
            id=f"{run_id}:{index}",
            sequence_number=index + 1,
            payload_json=canonical_payload,
            previous_hash=previous_hash,
            record_hash=record_hash,
        )
        records.append(record)
        previous_hash = record_hash
        evidence_bytes += len(json.dumps(
            {
                "id": record.id,
                "sequence_number": record.sequence_number,
                "payload_json": record.payload_json,
                "previous_hash": record.previous_hash,
                "record_hash": record.record_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"))
        total_generation_ms += (time.perf_counter() - started) * 1000

    if full_provenance:
        lineage_started = time.perf_counter()
        for manifest in lineage_artifacts or []:
            canonical_manifest = canonicalize(manifest)
            lineage_bytes += len(canonical_manifest.encode("utf-8"))
        lineage_generation_ms = (time.perf_counter() - lineage_started) * 1000
    else:
        lineage_generation_ms = 0.0
    verify_started = time.perf_counter()
    verification = verify_ledger(records)
    verification_ms = (time.perf_counter() - verify_started) * 1000
    return {
        "records": len(records),
        "generation_ms": total_generation_ms,
        "lineage_generation_ms": lineage_generation_ms,
        "verification_ms": verification_ms,
        "evidence_storage_bytes": evidence_bytes,
        "lineage_storage_bytes": lineage_bytes,
        "storage_bytes": evidence_bytes + lineage_bytes,
        "verified": verification.verified,
        "verification_checked_records": verification.checked_count,
        "record_hash": records[-1].record_hash if records else None,
    }


def _arm_delta(
    arm_metrics: dict[str, float],
    baseline_metrics: dict[str, float],
) -> dict[str, float | None]:
    return {
        metric: (
            round(arm_metrics[metric] - baseline_metrics[metric], 6)
            if metric in arm_metrics and metric in baseline_metrics
            else None
        )
        for metric in ("precision", "recall", "f1", "f1_macro", "pr_auc")
    }


def _lineage_manifests(
    *,
    run_id: str,
    raw_dataset_hash: str,
    validated_dataset_hash: str,
    processed_dataset_hash: str,
    training_config_hash: str,
    model_hash: str,
    prediction_hash: str,
    explanation_hash: str,
    results_hash: str,
) -> list[dict[str, Any]]:
    created_at = datetime.now(timezone.utc).isoformat()
    commit = os.environ.get("GITHUB_SHA") or os.environ.get("GIT_COMMIT")
    artifact_specs = (
        ("raw_dataset", None, raw_dataset_hash),
        ("validated_dataset", "raw_dataset", validated_dataset_hash),
        ("processed_dataset", "validated_dataset", processed_dataset_hash),
        ("training_configuration", "processed_dataset", training_config_hash),
        ("model", "training_configuration", model_hash),
        ("prediction", "model", prediction_hash),
        ("explanation", "prediction", explanation_hash),
        ("experiment", "explanation", sha256_hash(run_id)),
        ("results", "experiment", results_hash),
        ("report", "results", results_hash),
    )
    return [
        {
            "artifact_id": f"{artifact_type}:{run_id}",
            "artifact_type": artifact_type,
            "parent_artifact_id": (
                f"{parent_type}:{run_id}" if parent_type else None
            ),
            "created_at": created_at,
            "version": "1",
            "sha256": digest,
            "git_commit": commit,
            "experiment_id": "EXP-F",
        }
        for artifact_type, parent_type, digest in artifact_specs
    ]


def run_ablation(
    n_samples: int = 1200,
    seed: int = 42,
    variants: list[str] | None = None,
    model_type: str = "random_forest",
    repeats: int = 3,
    explanation_samples: int = 1,
) -> dict[str, Any]:
    """Compare A–E on identical fitted models, splits, and predictions per run.

    Classification scores are therefore expected to be equal across arms:
    XAI and evidence are post-prediction features, not model interventions.
    """
    if n_samples < 40:
        raise ValueError("n_samples must be at least 40.")
    if repeats < 1:
        raise ValueError("repeats must be at least 1.")
    if explanation_samples < 1:
        raise ValueError("explanation_samples must be at least 1.")
    if model_type not in {"random_forest", "logistic_regression"}:
        raise ValueError("model_type must be 'random_forest' or 'logistic_regression'.")

    selected_input = list(ARMS) if variants is None else list(variants)
    canonical_arms: list[str] = []
    for variant in selected_input:
        normalized = _LEGACY_ARMS.get(variant, variant)
        if normalized not in ARMS:
            raise ValueError(
                f"Unknown ablation variant '{variant}'. Supported: {', '.join(ARMS)}."
            )
        if normalized not in canonical_arms:
            canonical_arms.append(normalized)
    if len(canonical_arms) < 1:
        raise ValueError("At least one ablation arm must be selected.")

    generated_frame = generate_flow_dataset(n_samples=n_samples, random_state=seed)
    raw_dataset_bytes = generated_frame.to_csv(index=False).encode("utf-8")
    frame, validation_report = validate_dataset(
        raw_dataset_bytes,
        file_name=f"exp_f_synthetic_seed_{seed}.csv",
        custom_target_column="label",
    )
    if not validation_report.valid:
        raise ValueError(
            "Generated ablation dataset failed validation: "
            + "; ".join(validation_report.errors)
        )
    feature_names = [column for column in frame.columns if column != "label"]
    X = frame[feature_names].to_numpy(dtype=np.float64)
    y = frame["label"].to_numpy()
    run_results: dict[str, list[dict[str, Any]]] = {
        arm: [] for arm in canonical_arms
    }

    for run_number in range(repeats):
        run_seed = seed + run_number
        X_train_raw, X_test_raw, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.25,
            random_state=run_seed,
            stratify=y,
        )
        # Fit preprocessing on training data only; all arms share the transform.
        means = X_train_raw.mean(axis=0)
        scales = X_train_raw.std(axis=0)
        scales[scales == 0] = 1.0
        X_train = (X_train_raw - means) / scales
        X_test = (X_test_raw - means) / scales

        classifier = _model(model_type, run_seed)
        classifier.fit(X_train, y_train)
        y_pred = classifier.predict(X_test)
        probabilities = classifier.predict_proba(X_test)
        classes = list(classifier.classes_)
        positive_class = classes.index(1) if 1 in classes else int(np.argmax(classes))
        y_probability = probabilities[:, positive_class]
        scores = _prediction_metrics(y_test, y_pred, y_probability)
        run_id = f"EXP-F-{run_seed}-{uuid4().hex[:8]}"

        inference_times: list[float] = []
        for _ in range(3):
            start = time.perf_counter()
            classifier.predict(X_test)
            inference_times.append((time.perf_counter() - start) * 1000 / len(X_test))
        inference_latency_ms = float(statistics.median(inference_times))
        _, peak_memory_mb = _memory_peak_mb(lambda: classifier.predict(X_test))

        for arm in canonical_arms:
            spec = ARMS[arm]
            explanation_times: list[float] = []
            top_features: list[dict[str, Any]] | None = None
            lineage_started_at = None

            if spec["xai"]:
                explainer_started = time.perf_counter()
                explainer = SHAPExplainer(
                    detector=_Probe(classifier),
                    X_background=X_train[: min(50, len(X_train))],
                    feature_names=feature_names,
                )
                explanation_setup_ms = (time.perf_counter() - explainer_started) * 1000
                representative = X_test[: min(explanation_samples, len(X_test))]
                try:
                    explanations = []
                    for sample in representative:
                        started = time.perf_counter()
                        explanations.append(explainer.explain(sample.reshape(1, -1)))
                        explanation_times.append(
                            (time.perf_counter() - started) * 1000
                        )
                    _, explanation_peak_memory_mb = _memory_peak_mb(
                        lambda: [
                            explainer.explain(sample.reshape(1, -1))
                            for sample in representative
                        ]
                    )
                    shap_result = explanations[0]
                    top_features = [
                        {
                            "feature": item.feature,
                            "shap_value": float(item.shap_value),
                            "importance": float(item.importance),
                        }
                        for item in shap_result.top_k(5)
                    ]
                except Exception as exc:
                    raise RuntimeError(
                        f"Ablation arm {arm} could not measure XAI: {exc}"
                    ) from exc
            else:
                explanation_setup_ms = None
                explanation_peak_memory_mb = 0.0

            evidence_result: dict[str, Any] | None = None
            evidence_peak_memory_mb = 0.0
            if spec["evidence"]:
                lineage_artifacts = None
                if spec["full_provenance"]:
                    lineage_started_at = time.perf_counter()
                    raw_hash = hashlib.sha256(raw_dataset_bytes).hexdigest()
                    validated_hash = hashlib.sha256(
                        frame.to_csv(index=False).encode("utf-8")
                    ).hexdigest()
                    processed_hash = hashlib.sha256(
                        X_train.tobytes()
                        + X_test.tobytes()
                        + y_train.tobytes()
                        + y_test.tobytes()
                    ).hexdigest()
                    config_hash = sha256_hash(canonicalize({
                        "model_type": model_type,
                        "seed": run_seed,
                        "model_parameters": classifier.get_params(deep=False),
                        "train_size": len(X_train),
                        "test_size": len(X_test),
                        "features": feature_names,
                        "preprocessing_mean": means.tolist(),
                        "preprocessing_scale": scales.tolist(),
                    }))
                    model_hash = hashlib.sha256(
                        pickle.dumps(classifier, protocol=5)
                    ).hexdigest()
                    prediction_hash = sha256_hash(canonicalize({
                        "classes": [int(value) for value in y_pred],
                        "ground_truth": [int(value) for value in y_test],
                        "positive_class_probabilities": [
                            float(value) for value in y_probability
                        ],
                    }))
                    explanation_hash = sha256_hash(canonicalize(top_features or []))
                    results_hash = sha256_hash(canonicalize(scores))
                    lineage_artifacts = _lineage_manifests(
                        run_id=run_id,
                        raw_dataset_hash=raw_hash,
                        validated_dataset_hash=validated_hash,
                        processed_dataset_hash=processed_hash,
                        training_config_hash=config_hash,
                        model_hash=model_hash,
                        prediction_hash=prediction_hash,
                        explanation_hash=explanation_hash,
                        results_hash=results_hash,
                    )
                evidence_result = _measure_evidence(
                    y_pred=y_pred,
                    y_probability=y_probability,
                    model_type=model_type,
                    run_id=run_id,
                    top_features=top_features,
                    full_provenance=spec["full_provenance"],
                    lineage_artifacts=lineage_artifacts,
                )
                _, evidence_peak_memory_mb = _memory_peak_mb(
                    lambda: _measure_evidence(
                        y_pred=y_pred,
                        y_probability=y_probability,
                        model_type=model_type,
                        run_id=run_id,
                        top_features=top_features,
                        full_provenance=spec["full_provenance"],
                        lineage_artifacts=lineage_artifacts,
                    )
                )
                if not evidence_result["verified"]:
                    raise RuntimeError(f"Ablation arm {arm} generated invalid evidence.")
                if lineage_started_at is not None:
                    evidence_result["lineage_generation_ms"] = (
                        time.perf_counter() - lineage_started_at
                    ) * 1000

            storage_bytes = evidence_result["storage_bytes"] if evidence_result else 0
            run_results[arm].append(
                {
                    "run": run_number + 1,
                    "seed": run_seed,
                    "trial_id": f"seed-{run_seed}",
                    "metrics": scores,
                    "inference_latency_ms_per_sample": inference_latency_ms,
                    "explanation_latency_ms_per_sample": (
                        float(statistics.median(explanation_times))
                        if explanation_times
                        else None
                    ),
                    "explanation_setup_ms": explanation_setup_ms,
                    "evidence_generation_latency_ms": (
                        evidence_result["generation_ms"] if evidence_result else None
                    ),
                    "lineage_generation_latency_ms": (
                        evidence_result["lineage_generation_ms"]
                        if evidence_result and spec["full_provenance"]
                        else None
                    ),
                    "verification_latency_ms": (
                        evidence_result["verification_ms"] if evidence_result else None
                    ),
                    "peak_traced_memory_mb": max(
                        peak_memory_mb,
                        explanation_peak_memory_mb,
                        evidence_peak_memory_mb,
                    ),
                    "evidence_storage_bytes": (
                        evidence_result["evidence_storage_bytes"] if evidence_result else 0
                    ),
                    "lineage_storage_bytes": (
                        evidence_result["lineage_storage_bytes"] if evidence_result else 0
                    ),
                    "storage_bytes": storage_bytes,
                    "evidence_verified": (
                        evidence_result["verified"] if evidence_result else None
                    ),
                    "verification_checked_records": (
                        evidence_result["verification_checked_records"]
                        if evidence_result
                        else 0
                    ),
                    "evidence_record_hash": (
                        evidence_result["record_hash"] if evidence_result else None
                    ),
                    "n_train": len(X_train),
                    "n_test": len(X_test),
                }
            )

    summarized: dict[str, dict[str, Any]] = {}
    performance_fields = (
        "inference_latency_ms_per_sample",
        "explanation_latency_ms_per_sample",
        "explanation_setup_ms",
        "evidence_generation_latency_ms",
        "lineage_generation_latency_ms",
        "verification_latency_ms",
        "peak_traced_memory_mb",
        "evidence_storage_bytes",
        "lineage_storage_bytes",
        "storage_bytes",
    )
    metric_names = ("accuracy", "precision", "recall", "f1", "f1_macro", "pr_auc", "roc_auc", "ece", "brier")
    for arm, entries in run_results.items():
        mean_metrics = {
            metric: _mean([entry["metrics"].get(metric) for entry in entries])
            for metric in metric_names
        }
        timing_summary = {}
        for field in performance_fields:
            observations = [
                entry[field] for entry in entries if entry[field] is not None
            ]
            trial_ids = [
                entry["trial_id"] for entry in entries if entry[field] is not None
            ]
            if observations:
                timing_summary[field] = bootstrap_trial_summary(
                    observations,
                    trial_ids,
                    raw_data_ref=f"/metrics/variants/{arm}/runs",
                    bootstrap_resamples=2000,
                    seed=seed + sum(field.encode("utf-8")),
                )
            else:
                timing_summary[field] = {
                    "method": "not applicable; no observations were collected",
                    "confidence_level": 0.95,
                    "bootstrap_resamples": 2000,
                    "n_trials": 0,
                    "n": 0,
                    "mean": None,
                    "sample_variance": None,
                    "sample_std": None,
                    "std": None,
                    "min": None,
                    "max": None,
                    "confidence_interval": None,
                    "raw_data_ref": f"/metrics/variants/{arm}/runs",
                    "raw_data_sha256": hashlib.sha256(b"[]").hexdigest(),
                    "raw_observations": [],
                    "limitations": "This measurement is not applicable to the selected arm.",
                }
        metric_statistics = {
            metric: bootstrap_trial_summary(
                [entry["metrics"][metric] for entry in entries],
                [entry["trial_id"] for entry in entries],
                raw_data_ref=f"/metrics/variants/{arm}/runs",
                bootstrap_resamples=2000,
                seed=seed + sum(metric.encode("utf-8")),
            )
            for metric in metric_names
        }
        summarized[arm] = {
            "name": ARMS[arm]["name"],
            "components": {
                "machine_learning": True,
                "preprocessing": True,
                "xai": ARMS[arm]["xai"],
                "cryptographic_evidence": ARMS[arm]["evidence"],
                "full_provenance_manifest": ARMS[arm]["full_provenance"],
            },
            "metrics": mean_metrics,
            "metric_statistics": metric_statistics,
            "metrics_ci95": {
                metric: metric_statistics[metric]["confidence_interval"]
                for metric in metric_names
            },
            "performance": timing_summary,
            "runs": entries,
        }

    baseline = summarized.get("A", summarized.get(canonical_arms[0], {}))
    full = summarized.get("E", {})
    deltas_vs_baseline = {
        arm: _arm_delta(data["metrics"], baseline.get("metrics", {}))
        for arm, data in summarized.items()
        if arm != ("A" if "A" in summarized else canonical_arms[0])
    }
    deltas_vs_full = {
        arm: _arm_delta(data["metrics"], full.get("metrics", {}))
        for arm, data in summarized.items()
        if arm != "E"
    } if full else {}
    baseline_arm = "A" if "A" in summarized else canonical_arms[0]
    paired_deltas_vs_baseline = {
        arm: {
            metric: paired_bootstrap_comparison(
                [entry["metrics"][metric] for entry in run_results[baseline_arm]],
                [entry["metrics"][metric] for entry in run_results[arm]],
                [entry["trial_id"] for entry in run_results[baseline_arm]],
                [entry["trial_id"] for entry in run_results[arm]],
                baseline_raw_data_ref=f"/metrics/variants/{baseline_arm}/runs",
                treatment_raw_data_ref=f"/metrics/variants/{arm}/runs",
                bootstrap_resamples=2000,
                seed=seed + sum(metric.encode("utf-8")),
            )
            for metric in ("precision", "recall", "f1", "f1_macro", "pr_auc")
        }
        for arm in summarized
        if arm != baseline_arm
    } if "A" in summarized else {}
    paired_deltas_vs_full = {
        arm: {
            metric: paired_bootstrap_comparison(
                [entry["metrics"][metric] for entry in run_results["E"]],
                [entry["metrics"][metric] for entry in run_results[arm]],
                [entry["trial_id"] for entry in run_results["E"]],
                [entry["trial_id"] for entry in run_results[arm]],
                baseline_raw_data_ref="/metrics/variants/E/runs",
                treatment_raw_data_ref=f"/metrics/variants/{arm}/runs",
                bootstrap_resamples=2000,
                seed=seed + sum(metric.encode("utf-8")),
            )
            for metric in ("precision", "recall", "f1", "f1_macro", "pr_auc")
        }
        for arm in summarized
        if arm != "E"
    } if "E" in summarized else {}
    report: dict[str, Any] = {
        "experiment_id": "EXP-F",
        "framework_version": "2",
        "title": "SentinelCrypt Component Ablation Study",
        "status": "COMPLETED",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "parameters": {
            "n_samples": n_samples,
            "random_state": seed,
            "model_type": model_type,
            "repeats": repeats,
            "statistical_methodology": {
                "trial_unit": "one complete train/test split and model fit identified by the trial seed",
                "confidence_intervals": "percentile bootstrap of trial-level means; 2,000 resamples; 95% interval",
                "pairing": "predictive metrics paired by identical trial seed, split, fitted model, and held-out predictions",
                "system_cost_comparison": "per-arm descriptive bootstrap summaries only; arms are not treated as randomized or order-controlled timing pairs",
                "effect_size": "Cohen's dz for paired predictive metric differences",
                "hypothesis_tests": "none; no p-values or significance claims are generated",
                "small_sample_caveat": "bootstrap intervals with few trial units are coarse and describe configured-run variability, not population-level uncertainty",
            },
            "explanation_samples_per_run": explanation_samples,
            "arms": canonical_arms,
            "shared_split_and_model_per_run": True,
        },
        "metrics": {
            "variants": summarized,
            "deltas_vs_A": deltas_vs_baseline if "A" in summarized else {},
            "deltas_vs_E": deltas_vs_full,
            "deltas_vs_full": deltas_vs_full,
            "paired_deltas_vs_A": paired_deltas_vs_baseline,
            "paired_deltas_vs_E": paired_deltas_vs_full,
            "performance_semantics": {
                "inference_latency_ms_per_sample": "Median of three whole-test-set predict calls, divided by test-set rows.",
                "explanation_latency_ms_per_sample": "Median per-sample SHAP explain() latency; explainer setup is reported separately.",
                "evidence_generation_latency_ms": "Total canonical JSON, SHA-256, and forward-chain construction time for each test prediction.",
                "lineage_generation_latency_ms": "Canonical serialization time for E-arm experiment provenance manifest entries.",
                "verification_latency_ms": "Elapsed verification time for the complete generated evidence chain.",
                "peak_traced_memory_mb": "Maximum isolated tracemalloc peak across inference, explanation, and evidence generation/verification; excludes model fitting and native allocations may be undercounted.",
                "storage_bytes": "Serialized payload/record bytes plus E-arm canonical lineage-manifest bytes; excludes DB/index/filesystem overhead.",
                "evidence_explanation_scope": "Only the first representative explanation is attached to the first evidence record; all configured representative samples are included in explanation-latency measurements.",
            },
            "interpretation": (
                "A–E share each run's trained model and held-out predictions. "
                "XAI/evidence are post-prediction and are not expected to improve "
                "precision, recall, F1, macro-F1, or PR-AUC. Differences in these "
                "scores indicate a measurement or implementation defect, not an "
                "assumed SentinelCrypt benefit."
            ),
        },
    }
    report["result_hash"] = sha256_hash(
        canonicalize({key: value for key, value in report.items() if key not in {"timestamp", "result_hash"}})
    )
    return report
