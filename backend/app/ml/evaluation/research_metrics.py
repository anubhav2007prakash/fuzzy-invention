"""Research measurement primitives — shared by benchmark, challenges, ablation.

Single owner of metric math so every research surface reports identical numbers:
  * detection quality   : F1, macro-F1, precision, recall, PR-AUC, accuracy
  * calibration         : Expected Calibration Error (ECE), Brier score
  * systems             : latency timing, peak-memory tracking (tracemalloc)
  * statistics           : mean/std/95% CI, paired t-test, Wilcoxon, effect size
"""
from __future__ import annotations

import statistics
import time
import tracemalloc
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

# ─────────────────────────────────────────────────────────────────────────────
# Detection metrics + calibration
# ─────────────────────────────────────────────────────────────────────────────

def expected_calibration_error(
    y_true: Sequence[int],
    y_prob: Sequence[float],
    n_bins: int = 10,
) -> float:
    """Binary ECE: confidence = P(predicted class), binned against accuracy."""
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob, dtype=float)
    if y_true.size == 0:
        return 0.0
    pred = (y_prob >= 0.5).astype(int)
    conf = np.where(pred == 1, y_prob, 1.0 - y_prob)
    acc = (pred == y_true).astype(float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (conf > lo) & (conf <= hi) if i > 0 else (conf >= lo) & (conf <= hi)
        if not mask.any():
            continue
        ece += (mask.sum() / len(y_true)) * abs(acc[mask].mean() - conf[mask].mean())
    return float(ece)


def classification_metrics(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    y_prob: Optional[Sequence[float]] = None,
) -> Dict[str, float]:
    """Full metric suite used by every benchmark-style evaluation."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    out: Dict[str, float] = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
    }
    if y_prob is not None and len(np.unique(y_true)) > 1:
        y_prob = np.asarray(y_prob, dtype=float)
        out["pr_auc"] = float(average_precision_score(y_true, y_prob))
        out["roc_auc"] = float(roc_auc_score(y_true, y_prob))
        out["brier"] = float(brier_score_loss(y_true, np.clip(y_prob, 0.0, 1.0)))
        out["ece"] = round(expected_calibration_error(y_true, y_prob), 6)
    else:
        out.update({"pr_auc": 0.0, "roc_auc": 0.0, "brier": 0.0, "ece": 0.0})
    return {k: round(v, 6) for k, v in out.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Systems measurement: latency and peak memory
# ─────────────────────────────────────────────────────────────────────────────

def time_ms(fn: Callable[[], Any]) -> Tuple[Any, float]:
    """Run fn, returning (result, elapsed_ms)."""
    start = time.perf_counter()
    result = fn()
    return result, (time.perf_counter() - start) * 1000.0


def time_median_ms(fn: Callable[[], Any], repeat: int = 3) -> Tuple[Any, float]:
    """Run fn `repeat` times; return last result and median elapsed ms."""
    samples: List[float] = []
    result = None
    for _ in range(max(1, repeat)):
        result, elapsed = time_ms(fn)
        samples.append(elapsed)
    return result, float(statistics.median(samples))


@contextmanager
def track_peak_memory_mb():
    """Context manager yielding a dict; `peak_mb` filled on exit (Python allocations)."""
    holder: Dict[str, float] = {"peak_mb": 0.0}
    already_running = tracemalloc.is_tracing()
    if not already_running:
        tracemalloc.start()
    try:
        yield holder
    finally:
        _, peak = tracemalloc.get_traced_memory()
        holder["peak_mb"] = round(peak / (1024 * 1024), 3)
        if not already_running:
            tracemalloc.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Statistics for repeated runs
# ─────────────────────────────────────────────────────────────────────────────

def summarize(values: Sequence[float]) -> Dict[str, Optional[float]]:
    """Legacy descriptive summary; use statistical_analysis for inference."""
    vals = [float(v) for v in values]
    n = len(vals)
    if n == 0:
        return {"n": 0, "mean": None, "std": None, "min": None, "max": None,
                "ci95_low": None, "ci95_high": None}
    mean = statistics.fmean(vals)
    std = statistics.stdev(vals) if n > 1 else 0.0
    return {
        "n": n,
        "mean": round(mean, 6),
        "std": round(std, 6),
        "min": round(min(vals), 6),
        "max": round(max(vals), 6),
        "ci95_low": None,
        "ci95_high": None,
    }


def paired_compare(
    baseline: Sequence[float],
    treatment: Sequence[float],
    trial_ids: Sequence[str],
    *,
    baseline_raw_data_ref: str,
    treatment_raw_data_ref: str,
    bootstrap_resamples: int = 5000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compatibility wrapper for an explicitly paired bootstrap comparison."""
    from backend.app.ml.evaluation.statistical_analysis import (
        paired_bootstrap_comparison,
    )

    return paired_bootstrap_comparison(
        baseline,
        treatment,
        trial_ids,
        trial_ids,
        baseline_raw_data_ref=baseline_raw_data_ref,
        treatment_raw_data_ref=treatment_raw_data_ref,
        bootstrap_resamples=bootstrap_resamples,
        seed=seed,
    )


def flatten_numeric(obj: Any, prefix: str = "") -> Dict[str, float]:
    """Flatten a nested result dict to dotted paths -> floats (for run-series stats)."""
    flat: Dict[str, float] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flat.update(flatten_numeric(value, path))
    elif isinstance(obj, bool):
        pass  # booleans are not run-series metrics
    elif isinstance(obj, (int, float)):
        flat[prefix] = float(obj)
    return flat
