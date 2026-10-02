"""EXP-H — Cross-Method Explanation Agreement experiment runner.

Trains the standard detector, computes SHAP / permutation / built-in importances
on the same holdout, and reports agreement (top-k overlap, Spearman, consensus).
Optionally repeats across noise levels to show whether agreement itself is stable.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.model_selection import train_test_split

from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hashing import sha256_hash
from backend.app.ml.data.synthetic import generate_flow_dataset
from backend.app.ml.evaluation.statistical_analysis import (
    descriptive_observation_summary,
)
from backend.app.xai.agreement import agreement_matrix, compute_importances

DEFAULT_NOISE_LEVELS = [0.0, 0.05, 0.10]


class _Probe:
    def __init__(self, model):
        self.raw_model = model
        self.model_type = "random_forest" if hasattr(model, "feature_importances_") else "logistic_regression"
        self.classes_ = getattr(model, "classes_", None)

    def predict(self, X):
        return self.raw_model.predict(X)

    def predict_proba(self, X):
        return self.raw_model.predict_proba(X)


def run_xai_agreement(
    n_samples: int = 800,
    top_k: int = 5,
    seed: int = 42,
    noise_levels: Optional[List[float]] = None,
    model_type: str = "random_forest",
) -> Dict[str, Any]:
    """Measure cross-method explanation agreement, optionally under noise."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression

    levels = list(noise_levels if noise_levels is not None else DEFAULT_NOISE_LEVELS)
    if not levels:
        raise ValueError("noise_levels must contain at least one level.")
    for level in levels:
        if level < 0:
            raise ValueError("noise_levels must be non-negative.")

    df = generate_flow_dataset(n_samples=n_samples, random_state=seed)
    feature_cols = [c for c in df.columns if c != "label"]
    X, y = df[feature_cols].values, df["label"].values
    X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=seed, stratify=y
    )

    if model_type == "logistic_regression":
        model = LogisticRegression(max_iter=500, random_state=seed)
    else:
        model = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=seed)
    model.fit(X_train, y_train)
    detector = _Probe(model)

    per_level: List[Dict[str, Any]] = []
    rng = np.random.RandomState(seed)

    for level in levels:
        X_eval = X_test if level == 0 else X_test + rng.normal(
            0, level, size=X_test.shape
        )
        methods = compute_importances(
            detector, X_eval, y_test, feature_cols, seed=seed
        )
        if len(methods) < 2:
            raise RuntimeError(
                "Fewer than two importance methods available — cannot measure agreement."
            )
        matrix = agreement_matrix(methods, top_k=top_k)
        per_level.append({
            "noise_std": level,
            "methods": matrix["methods"],
            "pairs": matrix["pairs"],
            "mean_topk_overlap": matrix["mean_topk_overlap"],
            "mean_spearman": round(
                float(np.mean([p["spearman"] for p in matrix["pairs"]])), 4
            ),
            "consensus_ranking": matrix["consensus_ranking"][:top_k],
            "features": matrix["features"],
        })

    overlap_series = [lvl["mean_topk_overlap"] for lvl in per_level]
    spearman_series = [lvl["mean_spearman"] for lvl in per_level]
    clean = per_level[0]

    # Does agreement persist under noise? (comparison vs zero-noise arm)
    agreement_stable = (
        min(overlap_series) >= 0.6 if len(overlap_series) > 1 else None
    )

    result = {
        "experiment_id": "EXP-H",
        "title": "Cross-Method Explanation Agreement",
        "status": "COMPLETED",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "parameters": {
            "n_samples": n_samples,
            "top_k": top_k,
            "random_state": seed,
            "model_type": model_type,
            "noise_levels": levels,
            "methods": clean["methods"],
        },
        "metrics": {
            "agreement_by_noise": per_level,
            "clean_agreement": {
                "mean_topk_overlap": clean["mean_topk_overlap"],
                "mean_spearman": clean["mean_spearman"],
                "pairs": clean["pairs"],
                "consensus_ranking": clean["consensus_ranking"],
            },
            "overlap_series": descriptive_observation_summary(
                overlap_series,
                [f"noise-{level}" for level in levels],
                raw_data_ref="$.metrics.agreement_by_noise[*].mean_topk_overlap",
                design="measurements across configured noise conditions",
                observation_type="condition",
            ),
            "spearman_series": descriptive_observation_summary(
                spearman_series,
                [f"noise-{level}" for level in levels],
                raw_data_ref="$.metrics.agreement_by_noise[*].mean_spearman",
                design="measurements across configured noise conditions",
                observation_type="condition",
            ),
            "agreement_stable_under_noise": agreement_stable,
            "interpretation": (
                f"Across {len(clean['methods'])} explanation methods, mean top-{top_k} "
                f"overlap is {clean['mean_topk_overlap']} (mean Spearman "
                f"{clean['mean_spearman']}) at zero noise."
                + (
                    f" Agreement {'holds' if agreement_stable else 'degrades'} "
                    "under feature noise."
                    if agreement_stable is not None else ""
                )
            ),
        },
    }
    result["result_hash"] = sha256_hash(canonicalize(
        {k: v for k, v in result.items() if k not in ("timestamp", "result_hash")}
    ))
    return result
