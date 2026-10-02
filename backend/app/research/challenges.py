"""Research Challenge framework (items: structured scientific investigation,
longitudinal runs, reproducibility challenge, preset research questions).

A challenge turns a question into a executed pipeline:

    Hypothesis -> Dataset -> Experimental configuration -> Repeated runs
        -> Statistical analysis -> Results -> Evidence -> Reproducibility package

Kinds:
    standard          — repeated runs of an experiment + mean/CI statistics
    longitudinal      — same protocol tracked across runs (variation, drift, runtime)
    reproducibility   — identical config rerun; determinism classification

Persisted under results/challenges/<id>.json.
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.app.core.config import settings
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hashing import sha256_hash
from backend.app.ml.evaluation.research_metrics import flatten_numeric
from backend.app.ml.evaluation.statistical_analysis import (
    bootstrap_trial_summary,
    descriptive_trial_summary,
)

RESULTS_DIR = Path(settings.RESULTS_DIR)
CHALLENGE_DIR = RESULTS_DIR / "challenges"

KINDS = ("standard", "longitudinal", "reproducibility")

# Item 27 — preset research questions Q1..Q5, each wired to a runnable challenge.
QUESTION_PRESETS: List[Dict[str, Any]] = [
    {
        "id": "Q1",
        "question": "How does explanation stability change under controlled perturbations of network-flow features?",
        "hypothesis": "SHAP attributions remain stable (cosine > 0.85) under low sensor noise and degrade gracefully as noise grows.",
        "kind": "standard",
        "experiment": "EXP-B",
        "default_config": {"noise_levels": [0.01, 0.05, 0.10, 0.20], "n_repetitions": 8, "random_state": 42},
        "metric_path": "metrics.overall_mean_stability",
    },
    {
        "id": "Q2",
        "question": "What computational overhead is introduced by cryptographically verifiable evidence generation?",
        "hypothesis": "Canonicalization + SHA-256 anchoring adds single-digit-microsecond cost per inference (<10% of pipeline).",
        "kind": "standard",
        "experiment": "EXP-D",
        "default_config": {"n_samples": 1500, "random_state": 42},
        "metric_path": "comparison.cryptographic_overhead.canonicalization_and_sha256_us",
    },
    {
        "id": "Q3",
        "question": "How does model calibration affect the reliability of security predictions?",
        "hypothesis": "ECE stays below 0.10 for the RF detector; miscalibration would signal overconfident attack scores.",
        "kind": "standard",
        "experiment": "BENCHMARK",
        "default_config": {"n_samples": 1200, "repeats": 3, "seed": 42},
        "metric_path": "summary.ece.mean",
    },
    {
        "id": "Q4",
        "question": "How does cross-dataset distribution shift affect both prediction performance and explanation stability?",
        "hypothesis": "Distribution shift degrades F1 by <15 points while explanation stability drops less than detection quality.",
        "kind": "standard",
        "experiment": "EXP-A",
        "default_config": {"n_samples": 1200, "random_state": 42},
        "metric_path": "metrics.generalization_gap.delta_f1",
    },
    {
        "id": "Q5",
        "question": "Can reproducibility metadata and cryptographic evidence improve independent verification of ML security experiments?",
        "hypothesis": "Runs with identical configuration and seed reproduce bit-identical canonical result hashes.",
        "kind": "reproducibility",
        "experiment": "EXP-A",
        "default_config": {"n_samples": 600, "random_state": 42},
        "metric_path": None,
    },
]


def _execute_once(experiment: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Run one iteration of the challenge's underlying operation."""
    if experiment == "BENCHMARK":
        from backend.app.research import benchmark
        return benchmark.run_benchmark(
            n_samples=int(config.get("n_samples", 1200)),
            seed=int(config.get("seed", config.get("random_state", 42))),
            repeats=1,
        )
    from backend.app.services.experiment_service import ExperimentService
    service = ExperimentService()
    return service.run_experiment_by_id(experiment, config=config)


def _dig(result: Dict[str, Any], path: Optional[str]) -> Optional[float]:
    if not path:
        return None
    node: Any = result
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return float(node) if isinstance(node, (int, float)) and not isinstance(node, bool) else None


def create_challenge(
    title: str,
    hypothesis: str,
    experiment: str,
    kind: str = "standard",
    config: Optional[Dict[str, Any]] = None,
    dataset_note: str = "Synthetic-scope protocol data (labelled synthetic).",
) -> Dict[str, Any]:
    """Define a challenge (item 2) — validation happens before any run."""
    if not title or not str(title).strip():
        raise ValueError("Challenge title must be a non-empty string.")
    if not hypothesis or len(str(hypothesis).strip()) < 10:
        raise ValueError("Hypothesis must be at least 10 characters.")
    if kind not in KINDS:
        raise ValueError(f"Unknown challenge kind '{kind}'. Supported: {', '.join(KINDS)}.")
    if not experiment:
        raise ValueError("Challenge must name an experiment (e.g. EXP-A) or BENCHMARK.")

    config = dict(config or {})
    seed = int(config.get("random_state", config.get("seed", 42)))
    return {
        "challenge_id": f"CH-{time.strftime('%Y%m%d-%H%M%S')}",
        "title": str(title).strip(),
        "hypothesis": str(hypothesis).strip(),
        "kind": kind,
        "experiment": experiment,
        "configuration": config,
        "seed": seed,
        "dataset": dataset_note,
        "status": "DEFINED",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def run_challenge(
    challenge: Dict[str, Any],
    n_runs: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute repeated runs → statistics → evidence → reproducibility package hooks."""
    kind = challenge["kind"]
    config = dict(challenge["configuration"])
    experiment = challenge["experiment"]
    seed = int(challenge.get("seed", 42))

    if kind == "reproducibility":
        n = max(2, int(n_runs or 3))
        runs = []
        trial_ids = []
        for i in range(n):
            cfg = dict(config)
            cfg["random_state"] = seed  # identical config every run — determinism probe
            cfg["seed"] = seed
            runs.append(_execute_once(experiment, cfg))
            trial_ids.append(f"repro-run-{i + 1}-seed-{seed}")
        hashes = [r.get("result_hash") for r in runs]
        metric_series = {
            path: [v for v in (_dig(r, path) for r in runs) if v is not None]
            for path in _interesting_paths(runs)
        }
        metric_series = {k: v for k, v in metric_series.items() if len(v) == n}
        stats = {
            path: descriptive_trial_summary(
                values,
                trial_ids,
                raw_data_ref=f"$.runs[*].{path}",
                design="identical-configuration reproducibility reruns",
            )
            for path, values in metric_series.items()
        }
        all_identical = len(set(h for h in hashes if h)) == 1 and None not in hashes
        deterministic_metrics = all(
            abs(max(v) - min(v)) < 1e-12 for v in metric_series.values()
        ) if metric_series else None
        analysis = {
            "runs": n,
            "result_hashes": hashes,
            "hash_identical_across_runs": all_identical,
            "metrics_deterministic": deterministic_metrics,
            "metric_stats": stats,
            "statistical_methodology": {
                "trial_unit": "one complete execution with identical configuration and seed",
                "analysis": "descriptive only; reruns are determinism probes, not independent trials",
                "hypothesis_tests": "none",
            },
            "determinism_classification": _classify_determinism(
                all_identical, deterministic_metrics),
        }
        challenge.update(_finish(challenge, runs, analysis, n))
        return challenge

    # standard + longitudinal: same pipeline, different analysis focus
    n = max(1, int(n_runs or int(config.pop("n_runs", 5))))
    runs: List[Dict[str, Any]] = []
    runtimes: List[float] = []
    trial_ids: List[str] = []
    for i in range(n):
        cfg = dict(config)
        if kind == "longitudinal" and config.get("vary_seed", False):
            trial_seed = seed + i
            cfg["random_state"] = trial_seed
            cfg["seed"] = trial_seed
        else:
            trial_seed = int(config.get("random_state", config.get("seed", seed)))
            cfg.setdefault("random_state", seed)
            cfg.setdefault("seed", seed)
        t0 = time.perf_counter()
        runs.append(_execute_once(experiment, cfg))
        runtimes.append((time.perf_counter() - t0) * 1000.0)
        trial_ids.append(f"run-{i + 1}-seed-{trial_seed}")

    paths = _interesting_paths(runs)
    metric_series = {
        path: [v for v in (_dig(r, path) for r in runs) if v is not None]
        for path in paths
    }
    metric_series = {k: v for k, v in metric_series.items() if len(v) == len(runs)}
    bootstrap_metrics = kind == "longitudinal" and bool(config.get("vary_seed", False))
    summary_function = (
        bootstrap_trial_summary if bootstrap_metrics else descriptive_trial_summary
    )
    stats = {
        path: summary_function(
            values,
            trial_ids,
            raw_data_ref=f"$.runs[*].{path}",
            **(
                {"bootstrap_resamples": 2000, "seed": seed}
                if bootstrap_metrics
                else {
                    "design": (
                        "repeated-seed runs"
                        if kind == "longitudinal"
                        else "same-configuration repeated executions"
                    )
                }
            ),
        )
        for path, values in metric_series.items()
    }

    analysis: Dict[str, Any] = {
        "runs": n,
        "metric_stats": stats,
        "runtime_ms": descriptive_trial_summary(
            runtimes,
            trial_ids,
            raw_data_ref="/analysis/raw_runtime_observations",
            design="ordered repeated wall-clock measurements; descriptive only",
        ),
        "statistical_methodology": {
            "trial_unit": "one complete challenge execution",
            "analysis": (
                "trial-level percentile bootstrap of means with 2,000 resamples "
                "and 95% intervals"
                if bootstrap_metrics
                else "descriptive summaries only; no confidence intervals or tests"
            ),
            "hypothesis_tests": "none",
        },
        "raw_runtime_observations": [
            {"trial_id": trial_id, "value": float(runtime_ms)}
            for trial_id, runtime_ms in zip(trial_ids, runtimes)
        ],
    }
    if len(runs) >= 3 and metric_series:
        # trend: slope of first metric across runs (drift indicator)
        first = next(iter(metric_series.values()))
        slope = float(
            (first[-1] - first[0]) / (len(first) - 1)
        ) if len(set(first)) > 1 else 0.0
        analysis["drift_slope_per_run"] = round(slope, 6)
        analysis["interpretation"] = (
            "Metric variation across repeated runs; non-zero drift slope indicates "
            "run-order dependence (seed variation or version drift)."
        )
    if kind == "standard" and len(runs) >= 2:
        hashes = [r.get("result_hash") for r in runs]
        analysis["hash_identical_across_runs"] = (
            len(set(h for h in hashes if h)) == 1 and None not in hashes
        )

    challenge.update(_finish(challenge, runs, analysis, n))
    return challenge


def _interesting_paths(runs: List[Dict[str, Any]]) -> List[str]:
    """Metric paths present in every run (stable across the series)."""
    if not runs:
        return []
    flats = [
        flatten_numeric({k: v for k, v in r.items()
                         if k in ("metrics", "comparison", "summary", "stages_ms")})
        for r in runs
    ]
    common = set(flats[0])
    for f in flats[1:]:
        common &= set(f)
    return sorted(common)


def _classify_determinism(hash_identical: Optional[bool],
                          metrics_deterministic: Optional[bool]) -> str:
    if hash_identical and metrics_deterministic:
        return ("fully_deterministic: canonical result hashes and all metrics "
                "reproduce bit-identically.")
    if metrics_deterministic:
        return ("metrics_deterministic: metrics reproduce exactly but envelope "
                "fields (timestamps/environment) differ between runs.")
    if hash_identical is False and metrics_deterministic is False:
        return "non_deterministic: metric values differ across identical-seed runs."
    return "inconclusive: not enough comparable metric series across runs."


def _finish(challenge: Dict[str, Any], runs: List[Dict[str, Any]],
            analysis: Dict[str, Any], n_runs: int) -> Dict[str, Any]:
    """Attach results, statistics, evidence hash, and persist to results/challenges."""
    canonical_runs = [
        {k: v for k, v in r.items() if k not in
         ("timestamp", "run_manifest", "reproducibility")}
        for r in runs
    ]
    evidence = {
        "challenge_id": challenge["challenge_id"],
        "n_runs": n_runs,
        "analysis": analysis,
    }
    CHALLENGE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        **challenge,
        "status": "COMPLETED",
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runs": canonical_runs,
        "analysis": analysis,
        "evidence_hash": sha256_hash(canonicalize(evidence)),
        "reproducibility_package": "available via /research/reproducibility/export",
    }
    path = CHALLENGE_DIR / f"{challenge['challenge_id']}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True, default=str)
    payload["persisted_to"] = path.as_posix()
    return payload


def list_challenges() -> List[Dict[str, Any]]:
    CHALLENGE_DIR.mkdir(parents=True, exist_ok=True)
    out: List[Dict[str, Any]] = []
    for path in sorted(CHALLENGE_DIR.glob("CH-*.json"), reverse=True):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.pop("runs", None)  # list view stays light
            out.append(data)
        except Exception:
            continue
    return out


def get_challenge(challenge_id: str) -> Optional[Dict[str, Any]]:
    path = CHALLENGE_DIR / f"{challenge_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_preset(preset_id: str, n_runs: Optional[int] = None) -> Dict[str, Any]:
    """Create + run one of the Q1..Q5 research-question presets end-to-end."""
    preset = next((p for p in QUESTION_PRESETS if p["id"].upper() == preset_id.upper()), None)
    if preset is None:
        raise ValueError(
            f"Unknown question preset '{preset_id}'. "
            f"Available: {', '.join(p['id'] for p in QUESTION_PRESETS)}."
        )
    challenge = create_challenge(
        title=f"{preset['id']}: {preset['question'][:80]}",
        hypothesis=preset["hypothesis"],
        experiment=preset["experiment"],
        kind=preset["kind"],
        config=dict(preset["default_config"]),
        dataset_note="Preset research question (synthetic-scope protocol data).",
    )
    challenge["question_id"] = preset["id"]
    challenge["question"] = preset["question"]
    return run_challenge(challenge, n_runs=n_runs)
