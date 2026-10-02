"""Design-explicit bootstrap summaries for repeated experiment observations.

No hypothesis test is selected or run implicitly. Each reported statistic carries
the raw-data references and a digest of the exact observations used to compute it.
"""
from __future__ import annotations

import hashlib
from typing import Any, Sequence

import numpy as np

from backend.app.cryptography.canonicalization import canonicalize


def _validate_trials(
    values: Sequence[float],
    trial_ids: Sequence[str],
    name: str,
) -> tuple[np.ndarray, list[str]]:
    if len(values) != len(trial_ids):
        raise ValueError(f"{name} values and trial_ids must have equal lengths.")
    if len(values) == 0:
        raise ValueError(f"{name} requires at least one trial.")
    if len(set(trial_ids)) != len(trial_ids):
        raise ValueError(f"{name} trial_ids must be unique.")
    numeric_values = np.asarray(values, dtype=float)
    if not np.isfinite(numeric_values).all():
        raise ValueError(f"{name} values must all be finite.")
    return numeric_values, [str(trial_id) for trial_id in trial_ids]


def _bootstrap_ci(
    values: np.ndarray,
    *,
    confidence_level: float,
    bootstrap_resamples: int,
    seed: int,
) -> dict[str, float] | None:
    if len(values) < 2:
        return None
    rng = np.random.default_rng(seed)
    sampled_indices = rng.integers(
        0, len(values), size=(bootstrap_resamples, len(values))
    )
    bootstrap_means = values[sampled_indices].mean(axis=1)
    alpha = 1.0 - confidence_level
    lower, upper = np.quantile(
        bootstrap_means, [alpha / 2.0, 1.0 - alpha / 2.0]
    )
    return {"low": float(lower), "high": float(upper)}


def _validate_bootstrap_options(
    confidence_level: float,
    bootstrap_resamples: int,
) -> None:
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0 and 1.")
    if bootstrap_resamples < 100:
        raise ValueError("bootstrap_resamples must be at least 100.")


def _raw_digest(observations: list[dict[str, Any]]) -> str:
    canonical = canonicalize(observations).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def descriptive_observation_summary(
    values: Sequence[float],
    observation_ids: Sequence[str],
    *,
    raw_data_ref: str,
    design: str = "descriptive observations",
    observation_type: str = "observation",
) -> dict[str, Any]:
    """Summarize observations without inferential intervals or test selection."""
    values_array, ids = _validate_trials(
        values, observation_ids, "descriptive summary"
    )
    observations = [
        {f"{observation_type}_id": observation_id, "value": float(value)}
        for observation_id, value in zip(ids, values_array)
    ]
    sample_variance = (
        float(values_array.var(ddof=1)) if len(values_array) > 1 else None
    )
    sample_std = (
        float(values_array.std(ddof=1)) if len(values_array) > 1 else None
    )
    count_field = f"n_{observation_type}s"
    return {
        "design": design,
        "method": "descriptive statistics only; no inferential interval or test",
        count_field: len(values_array),
        "n": len(values_array),
        "mean": float(values_array.mean()),
        "sample_variance": sample_variance,
        "sample_std": sample_std,
        "std": sample_std,
        "min": float(values_array.min()),
        "max": float(values_array.max()),
        "confidence_interval": None,
        "raw_data_ref": raw_data_ref,
        "raw_data_sha256": _raw_digest(observations),
        "raw_observations": observations,
        "p_value": None,
        "significance_claim": None,
    }


def descriptive_trial_summary(
    values: Sequence[float],
    trial_ids: Sequence[str],
    *,
    raw_data_ref: str,
    design: str = "descriptive trial observations",
) -> dict[str, Any]:
    return descriptive_observation_summary(
        values,
        trial_ids,
        raw_data_ref=raw_data_ref,
        design=design,
        observation_type="trial",
    )


def bootstrap_trial_summary(
    values: Sequence[float],
    trial_ids: Sequence[str],
    *,
    raw_data_ref: str,
    bootstrap_resamples: int = 5000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> dict[str, Any]:
    """Describe repeat-level values with a percentile bootstrap CI of the mean.

    The resampling unit is one complete trial, not an individual row or timing
    sample. A single trial has no estimated variance or confidence interval.
    """
    _validate_bootstrap_options(confidence_level, bootstrap_resamples)
    values_array, ids = _validate_trials(values, trial_ids, "bootstrap summary")
    observations = [
        {"trial_id": trial_id, "value": float(value)}
        for trial_id, value in zip(ids, values_array)
    ]
    interval = _bootstrap_ci(
        values_array,
        confidence_level=confidence_level,
        bootstrap_resamples=bootstrap_resamples,
        seed=seed,
    )
    return {
        "method": "trial-level percentile bootstrap of the arithmetic mean",
        "confidence_level": confidence_level,
        "bootstrap_resamples": bootstrap_resamples,
        "bootstrap_seed": seed,
        "n_trials": len(values_array),
        "n": len(values_array),
        "mean": float(values_array.mean()),
        "sample_variance": (
            float(values_array.var(ddof=1)) if len(values_array) > 1 else None
        ),
        "sample_std": (
            float(values_array.std(ddof=1)) if len(values_array) > 1 else None
        ),
        "std": (
            float(values_array.std(ddof=1)) if len(values_array) > 1 else None
        ),
        "min": float(values_array.min()),
        "max": float(values_array.max()),
        "confidence_interval": interval,
        "raw_data_ref": raw_data_ref,
        "raw_data_sha256": _raw_digest(observations),
        "raw_observations": observations,
        "limitations": (
            "Interval describes variability across observed trials only; it is not "
            "a population-level guarantee. Bootstrap precision is limited when "
            "few independent trial units are available."
        ),
    }


def paired_bootstrap_comparison(
    baseline: Sequence[float],
    treatment: Sequence[float],
    baseline_trial_ids: Sequence[str],
    treatment_trial_ids: Sequence[str],
    *,
    baseline_raw_data_ref: str,
    treatment_raw_data_ref: str,
    bootstrap_resamples: int = 5000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> dict[str, Any]:
    """Estimate paired mean difference and Cohen's dz without a p-value.

    Pairing is explicit and strict: each arm must have the same ordered trial IDs.
    This procedure reports an interval and effect size; it does not declare
    significance or select a hypothesis test.
    """
    _validate_bootstrap_options(confidence_level, bootstrap_resamples)
    baseline_values, baseline_ids = _validate_trials(
        baseline, baseline_trial_ids, "baseline"
    )
    treatment_values, treatment_ids = _validate_trials(
        treatment, treatment_trial_ids, "treatment"
    )
    if baseline_ids != treatment_ids:
        raise ValueError("Paired comparison requires matching ordered trial_ids.")

    differences = treatment_values - baseline_values
    observations = [
        {
            "trial_id": trial_id,
            "baseline": float(base),
            "treatment": float(treat),
            "difference_treatment_minus_baseline": float(difference),
        }
        for trial_id, base, treat, difference in zip(
            baseline_ids, baseline_values, treatment_values, differences
        )
    ]
    difference_std = (
        float(differences.std(ddof=1)) if len(differences) > 1 else None
    )
    return {
        "design": "paired repeated trials",
        "method": "trial-level paired percentile bootstrap of mean difference",
        "confidence_level": confidence_level,
        "bootstrap_resamples": bootstrap_resamples,
        "bootstrap_seed": seed,
        "n_pairs": len(differences),
        "mean_difference_treatment_minus_baseline": float(differences.mean()),
        "sample_variance_of_differences": (
            float(differences.var(ddof=1)) if len(differences) > 1 else None
        ),
        "sample_std_of_differences": difference_std,
        "confidence_interval": _bootstrap_ci(
            differences,
            confidence_level=confidence_level,
            bootstrap_resamples=bootstrap_resamples,
            seed=seed,
        ),
        "cohens_dz": (
            float(differences.mean() / difference_std)
            if difference_std is not None and difference_std > 0
            else None
        ),
        "effect_size_method": "Cohen's dz: mean paired difference / sample SD of paired differences",
        "raw_data_refs": [
            baseline_raw_data_ref,
            treatment_raw_data_ref,
        ],
        "raw_data_sha256": _raw_digest(observations),
        "raw_observations": observations,
        "p_value": None,
        "significance_claim": None,
        "limitations": (
            "A percentile bootstrap interval and standardized paired effect size "
            "are descriptive; no hypothesis test or significance threshold was "
            "prespecified or applied."
        ),
    }


def independent_bootstrap_comparison(
    baseline: Sequence[float],
    treatment: Sequence[float],
    baseline_trial_ids: Sequence[str],
    treatment_trial_ids: Sequence[str],
    *,
    baseline_raw_data_ref: str,
    treatment_raw_data_ref: str,
    bootstrap_resamples: int = 5000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> dict[str, Any]:
    """Estimate independent-trial mean difference with a Welch-style bootstrap.

    Baseline and treatment trials are resampled independently. This is not a
    paired test and deliberately emits no p-value or significance decision.
    """
    _validate_bootstrap_options(confidence_level, bootstrap_resamples)
    baseline_values, baseline_ids = _validate_trials(
        baseline, baseline_trial_ids, "baseline"
    )
    treatment_values, treatment_ids = _validate_trials(
        treatment, treatment_trial_ids, "treatment"
    )
    observations = {
        "baseline": [
            {"trial_id": trial_id, "value": float(value)}
            for trial_id, value in zip(baseline_ids, baseline_values)
        ],
        "treatment": [
            {"trial_id": trial_id, "value": float(value)}
            for trial_id, value in zip(treatment_ids, treatment_values)
        ],
    }
    interval = None
    if len(baseline_values) > 1 and len(treatment_values) > 1:
        rng = np.random.default_rng(seed)
        baseline_indices = rng.integers(
            0, len(baseline_values),
            size=(bootstrap_resamples, len(baseline_values)),
        )
        treatment_indices = rng.integers(
            0, len(treatment_values),
            size=(bootstrap_resamples, len(treatment_values)),
        )
        differences = (
            treatment_values[treatment_indices].mean(axis=1)
            - baseline_values[baseline_indices].mean(axis=1)
        )
        alpha = 1.0 - confidence_level
        lower, upper = np.quantile(
            differences, [alpha / 2.0, 1.0 - alpha / 2.0]
        )
        interval = {"low": float(lower), "high": float(upper)}

    pooled_sd = None
    if len(baseline_values) > 1 and len(treatment_values) > 1:
        degrees = len(baseline_values) + len(treatment_values) - 2
        pooled_variance = (
            (len(baseline_values) - 1) * baseline_values.var(ddof=1)
            + (len(treatment_values) - 1) * treatment_values.var(ddof=1)
        ) / degrees
        pooled_sd = float(np.sqrt(pooled_variance))

    return {
        "design": "independent repeated trials",
        "method": "independent trial-level percentile bootstrap of difference in means",
        "confidence_level": confidence_level,
        "bootstrap_resamples": bootstrap_resamples,
        "bootstrap_seed": seed,
        "n_baseline": len(baseline_values),
        "n_treatment": len(treatment_values),
        "baseline_mean": float(baseline_values.mean()),
        "treatment_mean": float(treatment_values.mean()),
        "mean_difference_treatment_minus_baseline": float(
            treatment_values.mean() - baseline_values.mean()
        ),
        "baseline_sample_variance": (
            float(baseline_values.var(ddof=1)) if len(baseline_values) > 1 else None
        ),
        "treatment_sample_variance": (
            float(treatment_values.var(ddof=1))
            if len(treatment_values) > 1
            else None
        ),
        "confidence_interval": interval,
        "cohens_d": (
            float((treatment_values.mean() - baseline_values.mean()) / pooled_sd)
            if pooled_sd is not None and pooled_sd > 0
            else None
        ),
        "effect_size_method": "Cohen's d using pooled within-group trial SD",
        "raw_data_refs": [
            baseline_raw_data_ref,
            treatment_raw_data_ref,
        ],
        "raw_data_sha256": _raw_digest([
            {"group": "baseline", **item}
            for item in observations["baseline"]
        ] + [
            {"group": "treatment", **item}
            for item in observations["treatment"]
        ]),
        "raw_observations": observations,
        "p_value": None,
        "significance_claim": None,
        "limitations": (
            "Independent bootstrap assumes trial units are independent within "
            "groups. Repeated seeds on a shared dataset may violate that assumption; "
            "interpret as variability across configured runs, not population inference."
        ),
    }
