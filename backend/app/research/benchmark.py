"""SentinelCrypt Benchmark — one standardized protocol across data sources.

Measures, per source (item 1):
    F1, macro-F1, precision/recall, PR-AUC, inference latency, memory usage,
    explanation stability, calibration (ECE/Brier), OOD performance,
    ledger verification overhead, reproducibility
and produces a single machine-generated benchmark report (JSON + Markdown).

Sources: UNSW-NB15 and CICIDS2017 currently run on *distribution-matched
synthetic proxies* (clearly labelled) because no real captures are bundled;
an uploaded dataset can be substituted via ``dataset_id``.  The report states
the data origin for every row — never pretends a proxy is a real capture.

Also provides:
    * pipeline stage timing   (item 9 — end-to-end latency breakdown)
    * scalability sweep       (item 8 — size ladder + per-size measurements)
    * leaderboard rows        (item 26 — transparent experimental table)
"""
from __future__ import annotations

import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

from backend.app.core.config import settings
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hashing import sha256_hash
from backend.app.cryptography.hash_chain import build_audit_record_hashes, GENESIS_PREVIOUS_HASH
from backend.app.cryptography.verifier import verify_ledger
from backend.app.ml.data.synthetic import generate_flow_dataset, SYNTHETIC_DISCLAIMER
from backend.app.ml.evaluation.research_metrics import (
    classification_metrics,
    track_peak_memory_mb,
)
from backend.app.xai.shap_explainer import SHAPExplainer
from backend.app.xai.stability import ExplanationStabilityAnalyzer

RESULTS_DIR = Path(settings.RESULTS_DIR)

# Source definitions: label + distribution parameters + honest origin label.
BENCHMARK_SOURCES = {
    "unsw_nb15": {
        "label": "UNSW-NB15 (distribution-matched synthetic proxy)",
        "origin": "synthetic_proxy",
        "params": {"shift_scale": 1.0, "attack_ratio": 0.45, "random_state": 42},
        "ood_params": {"shift_scale": 1.65, "attack_ratio": 0.35, "random_state": 43},
        "note": "UNSW-NB15-like feature distributions. Not real UNSW-NB15 capture data.",
    },
    "cicids2017": {
        "label": "CICIDS2017 (distribution-matched synthetic proxy)",
        "origin": "synthetic_proxy",
        "params": {"shift_scale": 0.6, "attack_ratio": 0.2, "random_state": 44},
        "ood_params": {"shift_scale": 1.4, "attack_ratio": 0.5, "random_state": 45},
        "note": "CICIDS2017-like class imbalance and flow durations. Not real CICIDS2017 data.",
    },
    "controlled": {
        "label": "Controlled test data (labelled synthetic)",
        "origin": "synthetic_controlled",
        "params": {"shift_scale": 1.0, "attack_ratio": 0.3, "random_state": 42},
        "ood_params": {"shift_scale": 1.8, "attack_ratio": 0.3, "random_state": 46},
        "note": SYNTHETIC_DISCLAIMER,
    },
}

PIPELINE_STAGES = (
    "dataset_ingestion",
    "preprocessing",
    "prediction",
    "shap",
    "evidence_generation",
    "ledger_write",
    "verification",
)

SCALABILITY_SIZES = (10_000, 50_000, 100_000, 250_000, 500_000, 1_000_000)

# Metrics that MUST reproduce bit-identically across same-seed reruns.
# Timing/memory fields are wall-clock measurements and are reported as series,
# never folded into the identity claim.
DETERMINISTIC_METRIC_KEYS = (
    "f1", "f1_macro", "precision", "recall", "pr_auc", "roc_auc",
    "ece", "brier", "explanation_stability", "n_train", "n_test",
)


def _deterministic_slice(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {key: metrics.get(key) for key in DETERMINISTIC_METRIC_KEYS}


def _load_source(source: str, n_samples: int, dataset_id: Optional[str],
                 db=None) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """Return (dataframe, provenance) for a benchmark source."""
    if dataset_id:
        from backend.app.db.repositories.dataset_repository import DatasetRepository
        record = DatasetRepository(db).get_by_id(dataset_id) if db else None
        if not record:
            raise ValueError(f"Dataset '{dataset_id}' not found.")
        csvs = sorted(Path(settings.DATA_RAW_DIR).glob("*.csv"))
        df = None
        for path in csvs:
            candidate = pd.read_csv(path)
            # registered file names are UUID-based; match by hash through service is
            # heavier — the repository records file_name directly:
            if path.name == record.file_name:
                df = candidate
                break
        if df is None:
            df = pd.read_csv(Path(settings.DATA_RAW_DIR) / record.file_name)
        provenance = {
            "id": record.id, "name": record.name, "origin": "uploaded",
            "sha256": record.file_hash, "rows_used": len(df),
            "note": "Registered dataset uploaded through the Datasets API.",
        }
        return df, provenance

    if source not in BENCHMARK_SOURCES:
        raise ValueError(
            f"Unknown benchmark source '{source}'. "
            f"Available: {', '.join(BENCHMARK_SOURCES)} (or pass dataset_id)."
        )
    spec = BENCHMARK_SOURCES[source]
    df = generate_flow_dataset(n_samples=n_samples, **spec["params"])
    provenance = {
        "id": source, "name": spec["label"], "origin": spec["origin"],
        "sha256": sha256_hash(canonicalize(
            {k: round(float(v), 6) if isinstance(v, float) else v
             for k, v in df.head(200).to_dict().items()}
        )),
        "rows_used": len(df),
        "note": spec["note"],
    }
    return df, provenance


def _fit_eval(
    df: pd.DataFrame,
    seed: int,
    stability_repetitions: int = 5,
) -> Dict[str, Any]:
    """Train RF, evaluate detection + calibration + latency + memory + stability."""
    feature_cols = [c for c in df.columns if c != "label"]
    df = df.dropna().reset_index(drop=True)
    X, y = df[feature_cols].values, df["label"].values
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=seed, stratify=y
    )

    model = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=seed)

    with track_peak_memory_mb() as train_mem:
        t0 = time.perf_counter()
        model.fit(X_train, y_train)
        train_ms = (time.perf_counter() - t0) * 1000.0

    with track_peak_memory_mb() as infer_mem:
        t0 = time.perf_counter()
        for _ in range(5):
            y_pred = model.predict(X_test)
        infer_ms = (time.perf_counter() - t0) * 1000.0 / 5

    y_prob = model.predict_proba(X_test)[:, 1]
    metrics = classification_metrics(y_test, y_pred, y_prob)
    metrics.update({
        "inference_latency_ms": round(infer_ms / len(X_test), 6),
        "inference_latency_ms_batch": round(infer_ms, 4),
        "train_time_ms": round(train_ms, 3),
        "train_peak_memory_mb": train_mem["peak_mb"],
        "infer_peak_memory_mb": infer_mem["peak_mb"],
        "n_train": len(X_train),
        "n_test": len(X_test),
    })

    # Explanation stability on one attack sample
    detector = _wrap_detector(model, seed)
    try:
        explainer = SHAPExplainer(
            detector=detector, X_background=X_test[:50], feature_names=feature_cols
        )
        attack_rows = X_test[y_test == 1]
        sample = attack_rows[:1] if len(attack_rows) else X_test[:1]
        analyzer = ExplanationStabilityAnalyzer(
            explainer=explainer, n_repetitions=stability_repetitions,
            noise_std=0.05, random_seed=seed,
        )
        t0 = time.perf_counter()
        report = analyzer.analyze(sample)
        stability_ms = (time.perf_counter() - t0) * 1000.0
        metrics["explanation_stability"] = round(report.stability_score, 4)
        metrics["explanation_time_ms"] = round(stability_ms, 3)
    except Exception as exc:  # stability must never sink the benchmark
        metrics["explanation_stability"] = None
        metrics["explanation_error"] = str(exc)

    return metrics


class _WrappedDetector:
    """Minimal BaseDetector-compatible adapter for a fitted sklearn classifier."""

    def __init__(self, model, seed: int):
        self.raw_model = model
        self.model_type = "random_forest" if hasattr(model, "feature_importances_") else "logistic_regression"
        self.random_seed = seed
        self.classes_ = getattr(model, "classes_", None)

    def predict(self, X):
        return self.raw_model.predict(X)

    def predict_proba(self, X):
        return self.raw_model.predict_proba(X)


def _wrap_detector(model, seed: int) -> _WrappedDetector:
    return _WrappedDetector(model, seed)


def _ledger_overhead(n_blocks: int = 100, seed: int = 42) -> Dict[str, Any]:
    """Build + verify a hash chain: append and verification cost per block."""
    rng = np.random.RandomState(seed)
    from types import SimpleNamespace

    records = []
    prev_hash = GENESIS_PREVIOUS_HASH
    t0 = time.perf_counter()
    for i in range(1, n_blocks + 1):
        payload = {
            "sequence_number": i,
            "predicted_class": int(rng.choice([0, 1])),
            "probability": round(float(rng.uniform(0.6, 0.99)), 4),
        }
        can_json, _, r_hash = build_audit_record_hashes(payload, prev_hash)
        records.append(SimpleNamespace(
            sequence_number=i, payload_json=can_json,
            previous_hash=prev_hash, record_hash=r_hash, payload=payload,
        ))
        prev_hash = r_hash
    build_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    result = verify_ledger(records)
    verify_ms = (time.perf_counter() - t0) * 1000.0

    return {
        "n_blocks": n_blocks,
        "chain_valid": result.verified,
        "build_total_ms": round(build_ms, 3),
        "append_us_per_block": round(build_ms * 1000 / n_blocks, 2),
        "verify_total_ms": round(verify_ms, 3),
        "verify_us_per_block": round(verify_ms * 1000 / n_blocks, 2),
    }


def run_protocol(
    source: str,
    n_samples: int = 1200,
    seed: int = 42,
    dataset_id: Optional[str] = None,
    db=None,
    stability_repetitions: int = 5,
) -> Dict[str, Any]:
    """Run the full SentinelCrypt protocol on one source and return its row."""
    df, provenance = _load_source(source, n_samples, dataset_id, db=db)
    in_dist = _fit_eval(df, seed, stability_repetitions)

    # OOD arm: same protocol on the source's shifted distribution (or uploaded → shift)
    if dataset_id:
        ood_df = generate_flow_dataset(n_samples=n_samples, shift_scale=1.7,
                                       attack_ratio=0.5, random_state=seed + 1)
        ood_label = "synthetic shifted partition (controlled distribution shift)"
    else:
        spec = BENCHMARK_SOURCES[source]
        ood_df = generate_flow_dataset(n_samples=n_samples, **spec["ood_params"])
        ood_label = f"shifted partition of {source}"

    # OOD = train in-dist model, evaluate on shifted data
    feature_cols = [c for c in df.columns if c != "label"]
    train = df.dropna()
    ood = ood_df.dropna()
    X_tr, X_trv, y_tr, y_trv = train_test_split(
        train[feature_cols].values, train["label"].values,
        test_size=0.25, random_state=seed, stratify=train["label"],
    )
    model = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=seed)
    model.fit(X_tr, y_tr)
    ood_pred = model.predict(ood[feature_cols].values)
    ood_prob = model.predict_proba(ood[feature_cols].values)[:, 1]
    ood_metrics = classification_metrics(ood["label"].values, ood_pred, ood_prob)
    ood_metrics["partition"] = ood_label

    ledger = _ledger_overhead(n_blocks=100, seed=seed)

    return {
        "source": source,
        "provenance": provenance,
        "in_distribution": in_dist,
        "out_of_distribution": ood_metrics,
        "generalization_gap": {
            "delta_f1": round(in_dist["f1"] - ood_metrics["f1"], 4),
            "delta_f1_macro": round(in_dist["f1_macro"] - ood_metrics["f1_macro"], 4),
            "delta_pr_auc": round(in_dist["pr_auc"] - ood_metrics["pr_auc"], 4),
        },
        "ledger_overhead": ledger,
    }


def run_benchmark(
    sources: Optional[List[str]] = None,
    n_samples: int = 1200,
    seed: int = 42,
    repeats: int = 2,
    dataset_id: Optional[str] = None,
    db=None,
) -> Dict[str, Any]:
    """Run the protocol across sources with `repeats` runs each → reproducibility stats.

    Reproducibility = spread of F1 across identical-seed reruns (should be ~0).
    """
    selected = sources or (["dataset"] if dataset_id else list(BENCHMARK_SOURCES))
    rows: List[Dict[str, Any]] = []
    repro: Dict[str, List[float]] = {}

    for source in selected:
        src_key = "dataset" if dataset_id else source
        runs = [run_protocol(source if not dataset_id else "controlled",
                             n_samples, seed, dataset_id=dataset_id, db=db)
                for _ in range(max(1, repeats))]
        best = runs[0]
        f1_series = [r["in_distribution"]["f1"] for r in runs]
        macro_series = [r["in_distribution"]["f1_macro"] for r in runs]
        identical = len({
            sha256_hash(canonicalize(_deterministic_slice(r["in_distribution"])))
            for r in runs
        }) == 1
        repro[src_key] = f1_series
        best["reproducibility"] = {
            "repeats": len(runs),
            "f1_series": [round(v, 6) for v in f1_series],
            "f1_macro_series": [round(v, 6) for v in macro_series],
            "f1_spread": round(max(f1_series) - min(f1_series), 6),
            "bit_identical_across_runs": identical,
            "identity_scope": (
                "deterministic quality metrics (F1, macro-F1, precision/recall, "
                "PR-AUC, ROC-AUC, ECE, Brier, explanation stability); latency and "
                "memory are wall-clock measurements and are never folded into "
                "the identity claim."
            ),
            "deterministic_seed": seed,
        }
        rows.append(best)

    summary = _summarize(rows)
    report = {
        "benchmark_id": f"BENCH-{time.strftime('%Y-%m-%d-%H%M%S')}",
        "protocol": {
            "metrics": [
                "f1", "f1_macro", "precision", "recall", "pr_auc", "roc_auc",
                "ece", "brier", "inference_latency_ms", "train/infer peak memory MB",
                "explanation_stability", "explanation_time_ms",
                "OOD delta_f1", "ledger append/verify us per block",
                "repeatability spread",
            ],
            "model": "RandomForestClassifier(n_estimators=50, max_depth=8)",
            "seed": seed,
            "n_samples_per_source": n_samples,
            "repeats": repeats,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "sources": rows,
        "summary": summary,
        "status": "COMPLETED",
    }
    report["report_hash"] = sha256_hash(canonicalize(report))
    _write_report(report)
    return report


def _summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    def collect(path_a: str, path_b: str = "") -> List[float]:
        vals = []
        for r in rows:
            v = r["in_distribution"].get(path_a)
            if isinstance(v, (int, float)):
                vals.append(float(v))
        return vals

    out: Dict[str, Any] = {}
    for metric in ("f1", "f1_macro", "precision", "recall", "pr_auc", "ece",
                   "inference_latency_ms", "explanation_stability"):
        vals = [v for v in collect(metric) if v is not None]
        if vals:
            out[metric] = {
                "mean": round(statistics.fmean(vals), 6),
                "min": round(min(vals), 6),
                "max": round(max(vals), 6),
            }
    gaps = [r["generalization_gap"]["delta_f1"] for r in rows]
    if gaps:
        out["mean_ood_f1_drop"] = round(statistics.fmean(gaps), 4)
    spreads = [r["reproducibility"]["f1_spread"] for r in rows if "reproducibility" in r]
    if spreads:
        out["max_repeatability_spread"] = round(max(spreads), 6)
    out["sources_evaluated"] = len(rows)
    return out


def _write_report(report: Dict[str, Any]) -> None:
    """Persist JSON + a machine-generated Markdown report."""
    import json
    reports_dir = RESULTS_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H%M%S", time.gmtime())
    json_path = reports_dir / f"benchmark_{stamp}.json"
    md_path = reports_dir / "benchmark_latest.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True, default=str)

    lines = [
        f"# SentinelCrypt Benchmark Report — {report['benchmark_id']}",
        "",
        f"Generated: {report['protocol']['generated_at']}  ",
        f"Model: `{report['protocol']['model']}`  ",
        f"Seed: {report['protocol']['seed']} · repeats: {report['protocol']['repeats']}  ",
        f"Report hash: `{report['report_hash']}`",
        "",
        "## Protocol metrics",
        ", ".join(report["protocol"]["metrics"]),
        "",
        "## Results",
        "",
        "| Source | Origin | F1 | Macro-F1 | Precision | Recall | PR-AUC | ECE | Latency ms | Stability | OOD ΔF1 | F1 spread |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in report["sources"]:
        ind = row["in_distribution"]
        repro = row.get("reproducibility", {})
        lines.append(
            f"| {row['provenance']['name']} | {row['provenance']['origin']} "
            f"| {ind['f1']:.4f} | {ind['f1_macro']:.4f} | {ind['precision']:.4f} "
            f"| {ind['recall']:.4f} | {ind['pr_auc']:.4f} | {ind['ece']:.4f} "
            f"| {ind['inference_latency_ms']:.4f} "
            f"| {ind.get('explanation_stability', 'n/a')} "
            f"| {row['generalization_gap']['delta_f1']:.4f} "
            f"| {repro.get('f1_spread', 'n/a')} |"
        )
    lines += ["", "## Summary", ""]
    for key, value in report["summary"].items():
        lines.append(f"- **{key}**: {value}")
    lines += [
        "",
        "> Data-origin note: proxy sources are distribution-matched synthetic data, "
        "clearly labelled — not real UNSW-NB15/CICIDS2017 captures.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")


def latest_report() -> Optional[Dict[str, Any]]:
    import json
    reports_dir = RESULTS_DIR / "reports"
    reports = sorted(reports_dir.glob("benchmark_*.json"))
    if not reports:
        return None
    with open(reports[-1], "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# Item 9 — pipeline stage benchmark
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline_benchmark(n_samples: int = 600, seed: int = 42) -> Dict[str, Any]:
    """Measure every pipeline stage in ms → end-to-end latency breakdown."""
    stages: Dict[str, float] = {}

    t0 = time.perf_counter()
    df = generate_flow_dataset(n_samples=n_samples, random_state=seed)
    feature_cols = [c for c in df.columns if c != "label"]
    stages["dataset_ingestion"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    X, y = df[feature_cols].values, df["label"].values
    X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=seed, stratify=y
    )
    stages["preprocessing"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    model = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=seed)
    model.fit(X_train, y_train)
    train_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    stages["prediction"] = (time.perf_counter() - t0) * 1000

    detector = _wrap_detector(model, seed)
    sample = X_test[:1]
    t0 = time.perf_counter()
    explainer = SHAPExplainer(detector=detector, X_background=X_test[:50],
                              feature_names=feature_cols)
    shap_result = explainer.explain(sample)
    stages["shap"] = (time.perf_counter() - t0) * 1000

    evidence = {
        "event_type": "INFERENCE",
        "features": {c: float(sample[0][i]) for i, c in enumerate(feature_cols)},
        "predicted_class": int(y_pred[0]),
        "probability": float(y_prob[0]),
        "top_feature": shap_result.top_k(1)[0].feature,
    }
    t0 = time.perf_counter()
    canonical = canonicalize(evidence)
    payload_hash = sha256_hash(canonical)
    stages["evidence_generation"] = (time.perf_counter() - t0) * 1000

    from types import SimpleNamespace
    t0 = time.perf_counter()
    can_json, _, r_hash = build_audit_record_hashes(evidence, GENESIS_PREVIOUS_HASH)
    record = SimpleNamespace(sequence_number=1, payload_json=can_json,
                             previous_hash=GENESIS_PREVIOUS_HASH,
                             record_hash=r_hash, payload=evidence)
    stages["ledger_write"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    verification = verify_ledger([record])
    stages["verification"] = (time.perf_counter() - t0) * 1000

    end_to_end = sum(stages.values())
    metrics = classification_metrics(y_test, y_pred, y_prob)
    return {
        "stages_ms": {k: round(v, 4) for k, v in stages.items()},
        "stage_order": list(PIPELINE_STAGES),
        "end_to_end_ms": round(end_to_end, 4),
        "training_ms_excluded": round(train_ms, 3),
        "xai_overhead_pct": round(100 * stages["shap"] / end_to_end, 2),
        "crypto_overhead_pct": round(
            100 * (stages["evidence_generation"] + stages["ledger_write"]
                   + stages["verification"]) / end_to_end, 2
        ),
        "detection_metrics": metrics,
        "payload_hash": payload_hash,
        "chain_valid": verification.verified,
        "n_samples": n_samples,
        "seed": seed,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Item 8 — scalability sweep
# ─────────────────────────────────────────────────────────────────────────────

def run_scalability(
    sizes: Optional[List[int]] = None,
    seed: int = 42,
    ledger_probe_size: int = 2000,
) -> Dict[str, Any]:
    """Measure training time, throughput, memory, explanation/ledger/DB cost per size."""
    ladder = [int(s) for s in (sizes or SCALABILITY_SIZES)]
    for s in ladder:
        if s <= 0:
            raise ValueError("Scalability sizes must be positive integers.")

    points: List[Dict[str, Any]] = []
    for n in ladder:
        df = generate_flow_dataset(n_samples=n, random_state=seed)
        feature_cols = [c for c in df.columns if c != "label"]
        X, y = df[feature_cols].values, df["label"].values
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=seed, stratify=y
        )

        model = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=seed)
        with track_peak_memory_mb() as mem:
            t0 = time.perf_counter()
            model.fit(X_train, y_train)
            train_s = time.perf_counter() - t0

            t0 = time.perf_counter()
            for _ in range(3):
                y_pred = model.predict(X_test)
            infer_s = (time.perf_counter() - t0) / 3

        throughput = len(X_test) / infer_s if infer_s > 0 else float("inf")
        y_prob = model.predict_proba(X_test)[:, 1]
        metrics = classification_metrics(y_test, y_pred, y_prob)

        # Explanation time on a single sample (SHAP cost is ~per-sample)
        exp_ms = None
        try:
            detector = _wrap_detector(model, seed)
            explainer = SHAPExplainer(detector=detector, X_background=X_test[:50],
                                      feature_names=feature_cols)
            t0 = time.perf_counter()
            explainer.explain(X_test[:1])
            exp_ms = round((time.perf_counter() - t0) * 1000, 3)
        except Exception:
            pass

        # Ledger + DB cost: build a fixed-size chain, measure per-block cost, then
        # project total ledger bytes for this dataset size.
        ledger = _ledger_overhead(n_blocks=min(ledger_probe_size, max(50, n // 100)),
                                  seed=seed)
        per_block_bytes = 256  # canonical payload + 2 hashes, empirically stable
        points.append({
            "n_samples": n,
            "train_time_s": round(train_s, 3),
            "predict_throughput_rows_per_s": round(throughput, 1),
            "peak_memory_mb": mem["peak_mb"],
            "explanation_time_ms": exp_ms,
            "ledger_append_us_per_block": ledger["append_us_per_block"],
            "ledger_verify_us_per_block": ledger["verify_us_per_block"],
            "db_size_bytes_projected": n * per_block_bytes,
            "f1": metrics["f1"],
            "inference_latency_ms": None,  # derived: 1e3/throughput
            "inference_latency_ms_per_row": round(1000.0 / throughput, 6) if throughput else None,
        })

    # Scaling exponents (log-log slope) — how cost grows with n
    def exponent(key_a: str, key_b: str) -> Optional[float]:
        xs, ys = [], []
        for p in points:
            a, b = p.get(key_a), p.get(key_b)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a > 0 and b > 0:
                xs.append(np.log(a))
                ys.append(np.log(b))
        if len(xs) >= 2:
            return round(float(np.polyfit(xs, ys, 1)[0]), 3)
        return None

    result = {
        "sizes": ladder,
        "points": points,
        "scaling_exponents": {
            "train_time_vs_n": exponent("n_samples", "train_time_s"),
            "peak_memory_vs_n": exponent("n_samples", "peak_memory_mb"),
            "db_size_vs_n": exponent("n_samples", "db_size_bytes_projected"),
        },
        "seed": seed,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "COMPLETED",
    }
    result["result_hash"] = sha256_hash(canonicalize(
        {k: v for k, v in result.items() if k != "generated_at"}
    ))

    import json
    out = RESULTS_DIR / "scalability.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Item 26 — leaderboard rows
# ─────────────────────────────────────────────────────────────────────────────

def leaderboard(
    dataset_filter: Optional[str] = None,
    model_filter: Optional[str] = None,
    experiment_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Transparent experimental table across stored experiment results + benchmarks."""
    import json
    from backend.app.services.experiment_service import EXPERIMENT_RESULT_FILES

    rows: List[Dict[str, Any]] = []

    for exp_id, filename in EXPERIMENT_RESULT_FILES.items():
        path = RESULTS_DIR / filename
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                result = json.load(f)
        except Exception:
            continue

        metrics = result.get("metrics") or {}
        comparison = result.get("comparison") or {}
        common = {
            "experiment": exp_id,
            "title": result.get("title"),
            "status": result.get("status"),
            "result_hash": result.get("result_hash"),
            "model": None,
            "dataset": "synthetic",
            "f1": None,
            "latency_us": None,
            "xai_stability": None,
        }
        if exp_id == "EXP-A":
            common.update(dataset="synthetic (source partition)",
                          f1=metrics.get("in_distribution", {}).get("f1_score"))
        elif exp_id == "EXP-B":
            common.update(model="random_forest",
                          xai_stability=metrics.get("overall_mean_stability"))
        elif exp_id == "EXP-D":
            best = max(
                (comparison.get("random_forest") or {}, comparison.get("logistic_regression") or {}),
                key=lambda c: c.get("f1_score") or 0,
            )
            model_name = "random_forest" if best is comparison.get("random_forest") else "logistic_regression"
            common.update(model=model_name, f1=best.get("f1_score"),
                          latency_us=best.get("inference_time_us"))
        elif exp_id in ("EXP-F", "EXP-G", "EXP-H"):
            common.update(model=result.get("parameters", {}).get("model_type", "random_forest"),
                          f1=(metrics.get("full", {}) or {}).get("f1")
                             if isinstance(metrics.get("full"), dict) else None,
                          xai_stability=result.get("parameters", {}).get("xai_stability"))
        elif exp_id == "EXP-ROBUSTNESS":
            common.update(
                model=result.get("parameters", {}).get("model_type"),
                f1=(metrics.get("baseline_metrics", {}).get("f1") or {}).get("mean"),
            )
        rows.append(common)

    bench = latest_report()
    if bench:
        for src in bench.get("sources", []):
            ind = src["in_distribution"]
            rows.append({
                "experiment": "BENCHMARK",
                "title": bench["benchmark_id"],
                "status": "COMPLETED",
                "result_hash": bench.get("report_hash"),
                "model": "random_forest",
                "dataset": src["provenance"]["name"],
                "f1": ind.get("f1"),
                "latency_us": round((ind.get("inference_latency_ms") or 0) * 1000, 2),
                "xai_stability": ind.get("explanation_stability"),
            })

    def matches(row: Dict[str, Any]) -> bool:
        if dataset_filter and dataset_filter.lower() not in (row.get("dataset") or "").lower():
            return False
        if model_filter and model_filter.lower() not in (row.get("model") or "").lower():
            return False
        if experiment_filter and experiment_filter.lower() not in (row.get("experiment") or "").lower():
            return False
        return True

    filtered = [r for r in rows if matches(r)]
    filtered.sort(key=lambda r: (r.get("f1") is None, -(r.get("f1") or 0)))
    return {
        "rows": filtered,
        "total": len(filtered),
        "filters": {
            "dataset": dataset_filter, "model": model_filter,
            "experiment": experiment_filter,
        },
        "note": (
            "Transparent experimental table of measured runs — not a universal "
            "'best model' claim. All rows are SentinelCrypt-protocol measurements."
        ),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
