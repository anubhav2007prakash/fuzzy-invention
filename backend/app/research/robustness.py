"""Offline bounded-perturbation sensitivity measurements for EXP-ROBUSTNESS."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hashing import sha256_hash
from backend.app.ml.data.synthetic import generate_flow_dataset
from backend.app.ml.evaluation.research_metrics import classification_metrics
from backend.app.ml.evaluation.statistical_analysis import (
    descriptive_observation_summary,
)
from backend.app.xai.shap_explainer import SHAPExplainer

MAX_EPSILON = 0.20
DEFAULT_EPSILON_LEVELS = [0.02, 0.05, 0.10, 0.20]
SUPPORTED_MODELS = {"random_forest", "logistic_regression"}


class _Probe:
    def __init__(self, model: Any, model_type: str):
        self.raw_model = model
        self.model_type = model_type
        self.classes_ = getattr(model, "classes_", None)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.raw_model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return self.raw_model.predict_proba(X)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a, norm_b = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return float(np.clip(np.dot(a, b) / (norm_a * norm_b), -1.0, 1.0))


def _model_for(model_type: str, seed: int) -> Any:
    if model_type == "random_forest":
        return RandomForestClassifier(
            n_estimators=50, max_depth=8, random_state=seed, n_jobs=1,
        )
    if model_type == "logistic_regression":
        return LogisticRegression(max_iter=1000, random_state=seed)
    raise ValueError(
        "model_type must be 'random_forest' or 'logistic_regression'."
    )


def _metric_summary(
    trials: Sequence[Dict[str, Any]],
    value_getter,
    *,
    raw_data_ref: str,
) -> Dict[str, Any]:
    return descriptive_observation_summary(
        [value_getter(trial) for trial in trials],
        [trial["trial_id"] for trial in trials],
        raw_data_ref=raw_data_ref,
        design=(
            "descriptive variation across randomized train/holdout partitions "
            "of one deterministic synthetic fixture"
        ),
        observation_type="trial",
    )


def run_robustness_study(
    n_samples: int = 800,
    n_probe: int = 25,
    epsilon_levels: Optional[List[float]] = None,
    seed: int = 42,
    with_explanations: bool = True,
    n_repeats: int = 5,
    model_type: str = "random_forest",
    experiment_id: str = "ROBUSTNESS",
) -> Dict[str, Any]:
    """Measure sensitivity to synthetic, range-bounded feature perturbations.

    Scaling is fitted independently on each training partition. Perturbation
    amplitudes are fractions of each feature's training-partition range. The
    holdout sample itself is not clipped, so naturally out-of-range holdout
    observations are not silently changed by a zero-perturbation baseline.
    """
    levels = [
        float(epsilon)
        for epsilon in (
            DEFAULT_EPSILON_LEVELS if epsilon_levels is None else epsilon_levels
        )
    ]
    if not levels:
        raise ValueError("epsilon_levels must be a non-empty list.")
    if len(set(levels)) != len(levels):
        raise ValueError("epsilon_levels must be unique.")
    if any(not np.isfinite(level) or not 0 < level <= MAX_EPSILON for level in levels):
        raise ValueError(
            f"epsilon must be in (0, {MAX_EPSILON}] — perturbations are bounded "
            "to the training feature range by design."
        )
    if not isinstance(n_samples, int) or isinstance(n_samples, bool) or n_samples < 40:
        raise ValueError("n_samples must be an integer of at least 40.")
    if not isinstance(n_probe, int) or isinstance(n_probe, bool) or n_probe < 1:
        raise ValueError("n_probe must be a positive integer.")
    if not isinstance(n_repeats, int) or isinstance(n_repeats, bool) or n_repeats < 1:
        raise ValueError("n_repeats must be a positive integer.")
    if model_type not in SUPPORTED_MODELS:
        raise ValueError(
            "model_type must be 'random_forest' or 'logistic_regression'."
        )

    frame = generate_flow_dataset(n_samples=n_samples, random_state=seed)
    feature_names = [column for column in frame.columns if column != "label"]
    raw_features = frame[feature_names].to_numpy(dtype=float)
    labels = frame["label"].to_numpy()
    trial_results: List[Dict[str, Any]] = []
    condition_trials: Dict[float, List[Dict[str, Any]]] = {
        epsilon: [] for epsilon in levels
    }

    for trial_index in range(n_repeats):
        trial_seed = seed + trial_index
        train_raw, test_raw, y_train, y_test = train_test_split(
            raw_features,
            labels,
            test_size=0.25,
            random_state=trial_seed,
            stratify=labels,
        )
        scaler = StandardScaler()
        train_features = scaler.fit_transform(train_raw)
        test_features = scaler.transform(test_raw)
        train_min = train_features.min(axis=0)
        train_max = train_features.max(axis=0)
        train_ranges = train_max - train_min

        model = _model_for(model_type, trial_seed)
        model.fit(train_features, y_train)
        probe_indices = np.random.RandomState(trial_seed).choice(
            len(test_features),
            size=min(n_probe, len(test_features)),
            replace=False,
        )
        probe = test_features[probe_indices]
        baseline_probabilities = model.predict_proba(test_features)
        baseline_predictions = model.predict(test_features)
        baseline_probe_predictions = baseline_predictions[probe_indices]
        baseline_probe_confidence = model.predict_proba(probe).max(axis=1)
        baseline_metrics = classification_metrics(
            y_test, baseline_predictions, baseline_probabilities[:, 1],
        )

        explainer = None
        baseline_explanations: Optional[List[np.ndarray]] = None
        if with_explanations:
            explainer = SHAPExplainer(
                detector=_Probe(model, model_type),
                X_background=train_features[: min(50, len(train_features))],
                feature_names=feature_names,
            )
            baseline_explanations = [
                np.asarray(
                    [item.shap_value for item in explainer.explain(sample[None, :]).contributions],
                    dtype=float,
                )
                for sample in probe
            ]

        trial_id = f"trial-{trial_index + 1}"
        perturbation_seed = seed + 1 + trial_index
        unit_noise = np.random.RandomState(perturbation_seed).uniform(
            -1.0, 1.0, size=test_features.shape
        )
        trial_results.append({
            "trial_id": trial_id,
            "random_state": trial_seed,
            "perturbation_seed": perturbation_seed,
            "n_probe": int(len(probe)),
            "baseline_metrics": baseline_metrics,
        })

        for epsilon in levels:
            noise = unit_noise * epsilon * train_ranges
            perturbed_features = test_features + noise
            observed_fraction = np.divide(
                np.abs(perturbed_features - test_features),
                train_ranges,
                out=np.zeros_like(perturbed_features),
                where=train_ranges > 0,
            )
            perturbed_predictions = model.predict(perturbed_features)
            perturbed_probabilities = model.predict_proba(perturbed_features)
            perturbed_probe_predictions = perturbed_predictions[probe_indices]
            perturbed_probe_confidence = model.predict_proba(
                perturbed_features[probe_indices]
            ).max(axis=1)
            perturbed_metrics = classification_metrics(
                y_test, perturbed_predictions, perturbed_probabilities[:, 1],
            )

            explanation_similarity = None
            if explainer is not None and baseline_explanations is not None:
                perturbed_explanations = [
                    np.asarray(
                        [
                            item.shap_value
                            for item in explainer.explain(
                                perturbed_features[index][None, :]
                            ).contributions
                        ],
                        dtype=float,
                    )
                    for index in probe_indices
                ]
                explanation_similarity = float(np.mean([
                    _cosine_similarity(before, after)
                    for before, after in zip(
                        baseline_explanations, perturbed_explanations
                    )
                ]))

            metric_changes = {
                metric_name: round(
                    perturbed_metrics[metric_name] - baseline_metrics[metric_name],
                    6,
                )
                for metric_name in baseline_metrics
            }
            condition_trials[epsilon].append({
                "trial_id": trial_id,
                "prediction_stability": float(np.mean(
                    perturbed_probe_predictions == baseline_probe_predictions
                )),
                "confidence_change": float(np.mean(
                    np.abs(
                        perturbed_probe_confidence - baseline_probe_confidence
                    )
                )),
                "explanation_stability": explanation_similarity,
                "maximum_perturbation_fraction_of_train_range": float(
                    observed_fraction.max(initial=0.0)
                ),
                "baseline_metrics": baseline_metrics,
                "perturbed_metrics": perturbed_metrics,
                "metric_changes": metric_changes,
            })

    baseline_summaries = {
        metric_name: _metric_summary(
            trial_results,
            lambda trial, name=metric_name: trial["baseline_metrics"][name],
            raw_data_ref=f"$.metrics.trials[*].baseline_metrics.{metric_name}",
        )
        for metric_name in trial_results[0]["baseline_metrics"]
    }
    conditions: List[Dict[str, Any]] = []
    curve: List[Dict[str, Any]] = []
    for condition_index, epsilon in enumerate(levels):
        observations = condition_trials[epsilon]
        trial_ids = [trial["trial_id"] for trial in observations]
        stability = descriptive_observation_summary(
            [trial["prediction_stability"] for trial in observations],
            trial_ids,
            raw_data_ref=f"$.metrics.conditions[{condition_index}].trials[*].prediction_stability",
            design="descriptive variation across randomized train/holdout partitions",
            observation_type="trial",
        )
        confidence_change = descriptive_observation_summary(
            [trial["confidence_change"] for trial in observations],
            trial_ids,
            raw_data_ref=f"$.metrics.conditions[{condition_index}].trials[*].confidence_change",
            design="descriptive variation across randomized train/holdout partitions",
            observation_type="trial",
        )
        explanation_values = [
            trial["explanation_stability"]
            for trial in observations
            if trial["explanation_stability"] is not None
        ]
        explanation_stability = (
            descriptive_observation_summary(
                explanation_values,
                trial_ids,
                raw_data_ref=f"$.metrics.conditions[{condition_index}].trials[*].explanation_stability",
                design="descriptive variation across randomized train/holdout partitions",
                observation_type="trial",
            )
            if explanation_values
            else None
        )
        metric_changes = {
            metric_name: descriptive_observation_summary(
                [trial["metric_changes"][metric_name] for trial in observations],
                trial_ids,
                raw_data_ref=(
                    f"$.metrics.conditions[{condition_index}].trials[*]"
                    f".metric_changes.{metric_name}"
                ),
                design="paired perturbed-minus-clean metric changes across "
                       "randomized train/holdout partitions",
                observation_type="trial",
            )
            for metric_name in observations[0]["metric_changes"]
        }
        max_fraction = max(
            trial["maximum_perturbation_fraction_of_train_range"]
            for trial in observations
        )
        condition = {
            "epsilon": epsilon,
            "prediction_stability": stability,
            "prediction_flip_rate": round(1.0 - stability["mean"], 6),
            "confidence_change": confidence_change,
            "explanation_stability": explanation_stability,
            "explanation_cosine_drop": (
                None if explanation_stability is None
                else round(1.0 - explanation_stability["mean"], 6)
            ),
            "maximum_perturbation_fraction_of_train_range": max_fraction,
            "metric_changes": metric_changes,
            "trials": observations,
        }
        conditions.append(condition)
        curve.append({
            "epsilon": epsilon,
            "prediction_flip_rate": condition["prediction_flip_rate"],
            "confidence_drift_mean": round(confidence_change["mean"], 6),
            "explanation_cosine_drop_mean": condition["explanation_cosine_drop"],
            "robustness_score": round(stability["mean"], 6),
            "repeats": n_repeats,
        })

    result = {
        "experiment_id": experiment_id,
        "title": "Offline Bounded-Perturbation Sensitivity Measurements",
        "status": "COMPLETED",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "parameters": {
            "n_samples": n_samples,
            "n_probe_requested": n_probe,
            "n_probe_actual": trial_results[0]["n_probe"],
            "epsilon_levels": levels,
            "max_epsilon": MAX_EPSILON,
            "n_repeats": n_repeats,
            "random_state": seed,
            "model_type": model_type,
            "explanations_measured": with_explanations,
            "data_source": "controlled_synthetic_fixture",
            "perturbation_definition": (
                "Per-feature uniform perturbation bounded by epsilon times that "
                "feature's training-partition range. Holdout values are not clipped "
                "to training bounds, avoiding an additional unbounded shift when "
                "a holdout value naturally lies outside the training range."
            ),
            "ethics_note": (
                "Offline evaluation uses only a controlled synthetic fixture; "
                "no external system is probed or attacked."
            ),
        },
        "methodology": {
            "preprocessing": "StandardScaler fitted on each training partition only.",
            "evaluation": (
                "Each condition is evaluated on the complete held-out partition; "
                "prediction and explanation stability use a deterministic probe "
                "subset drawn from that partition."
            ),
            "statistical_reporting": (
                "Descriptive trial-level summaries only. No significance tests or "
                "population-level robustness claims are made."
            ),
        },
        "interpretation": (
            "These are bounded sensitivity measurements on a deterministic "
            "synthetic fixture, not evidence of generalization to real data and "
            "not a robustness guarantee. No robustness claim is made."
        ),
        "metrics": {
            "baseline_metrics": baseline_summaries,
            "conditions": conditions,
            "trials": trial_results,
            "curve": curve,
            "robustness_at_lowest_epsilon": (
                curve[0]["robustness_score"] if curve else None
            ),
            "robustness_at_highest_epsilon": (
                curve[-1]["robustness_score"] if curve else None
            ),
            "flip_rate_series": descriptive_observation_summary(
                [point["prediction_flip_rate"] for point in curve],
                [f"epsilon-{point['epsilon']}" for point in curve],
                raw_data_ref="$.metrics.curve[*].prediction_flip_rate",
                design="measurements across configured perturbation conditions",
                observation_type="condition",
            ),
        },
    }
    result["result_hash"] = sha256_hash(canonicalize({
        key: value for key, value in result.items()
        if key not in ("timestamp", "result_hash")
    }))
    return result
