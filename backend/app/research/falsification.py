"""Falsification Lab — Allows researchers to deliberately attempt to disprove
SentinelCrypt research claims.

Each falsification experiment supports:
- claim_selection
- baseline_configuration
- alternative_configuration
- alternative_dataset
- controlled_perturbation
- repeated_runs
- metrics
- statistical_analysis
- acceptance_criteria
- evidence_generation
- reproducibility_metadata

Produces per experiment:
- configuration
- provenance
- raw_results
- derived_metrics
- plots
- evidence
- conclusion_status (SUPPORTED / PARTIALLY_SUPPORTED / NOT_SUPPORTED / INCONCLUSIVE)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

from backend.app.core.config import settings
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hashing import sha256_hash
from backend.app.db.database import SessionLocal, get_db
from backend.app.db.models import FalsificationExperiment, FalsificationResult, Dataset
from backend.app.ml.data.synthetic import generate_flow_dataset
from backend.app.ml.evaluation.research_metrics import classification_metrics
from backend.app.ml.evaluation.statistical_analysis import (
    independent_bootstrap_comparison,
)
from backend.app.ml.models.random_forest import RandomForestDetector
from backend.app.xai.shap_explainer import SHAPExplainer
from backend.app.xai.stability import ExplanationStabilityAnalyzer

RESULTS_DIR = Path(settings.RESULTS_DIR)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

CONCLUSION_STATUSES = ("SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_SUPPORTED", "INCONCLUSIVE")


def _deterministic_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Extract deterministic metric keys for reproducibility hashing."""
    keys = ("f1", "f1_macro", "precision", "recall", "pr_auc", "roc_auc", "ece", "brier")
    return {key: metrics.get(key) for key in keys if key in metrics}


def _load_dataset(
    dataset_id: str, db=None
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """Load a registered dataset by ID."""
    from backend.app.db.repositories.dataset_repository import DatasetRepository
    record = DatasetRepository(db).get_by_id(dataset_id) if db else None
    if not record:
        raise ValueError(f"Dataset '{dataset_id}' not found.")
    csvs = sorted(Path(settings.DATA_RAW_DIR).glob("*.csv"))
    df = None
    for path in csvs:
        if path.name == record.file_name:
            df = pd.read_csv(path)
            break
    if df is None:
        df = pd.read_csv(Path(settings.DATA_RAW_DIR) / record.file_name)
    provenance = {
        "id": record.id,
        "name": record.name,
        "origin": "uploaded",
        "sha256": record.file_hash,
        "rows_used": len(df),
        "note": "Registered dataset uploaded through the Datasets API.",
    }
    return df, provenance


def run_falsification_experiment(
    experiment_id: str,
    baseline_config: Dict[str, Any],
    alternative_config: Dict[str, Any],
    perturbation_config: Dict[str, Any],
    n_repeats: int = 3,
    db=None,
) -> Dict[str, Any]:
    """Execute a full falsification experiment.

    The experiment attempts to disprove a research claim by comparing:
    - Baseline configuration (original claim)
    - Alternative configuration (perturbed/model/split)
    - Controlled perturbation applied to data

    Returns a complete result with configuration, provenance, raw results,
    derived metrics, plots, evidence, and conclusion status.
    """

    session = db or SessionLocal()
    owns_session = db is None
    experiment_started = time.perf_counter()

    try:
        # Load the experiment definition
        experiment = session.get(FalsificationExperiment, experiment_id)
        if not experiment:
            raise ValueError(f"FalsificationExperiment '{experiment_id}' not found.")

        claim_id = experiment.claim_id
        claim_statement = experiment.claim_statement

        # Determine datasets
        baseline_dataset_id = None
        alt_dataset_id = experiment.alternative_dataset_id

        # Load baseline dataset
        if baseline_dataset_id:
            baseline_df, baseline_provenance = _load_dataset(baseline_dataset_id, db=session)
        else:
            # Use synthetic default
            baseline_df, baseline_provenance = generate_flow_dataset(
                n_samples=1000, random_state=experiment.random_seed
            )

        # Load alternative dataset if specified
        if alt_dataset_id:
            alternative_df, alternative_provenance = _load_dataset(alt_dataset_id, db=session)
        else:
            # Generate alternative from different params
            alternative_df, alternative_provenance = generate_flow_dataset(
                n_samples=1000,
                random_state=experiment.random_seed + 100,
                shift_scale=1.7,
                attack_ratio=0.5,
            )

        feature_cols = [c for c in baseline_df.columns if c != "label"]

        # === Baseline Run ===
        baseline_metrics_list: List[Dict[str, Any]] = []
        baseline_raw_list: List[Any] = []

        for repeat in range(max(1, n_repeats)):
            seed = experiment.random_seed + repeat * 1000

            # Train baseline model
            rng = np.random.RandomState(seed)
            df = baseline_df.dropna().reset_index(drop=True)
            X, y = df[feature_cols].values, df["label"].values
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.25, random_state=seed, stratify=y
            )

            model = RandomForestClassifier(
                n_estimators=50, max_depth=8, random_state=seed
            )
            t0 = time.perf_counter()
            model.fit(X_train, y_train)
            train_time = (time.perf_counter() - t0) * 1000

            # Evaluate baseline
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)[:, 1]
            metrics = classification_metrics(y_test, y_pred, y_prob)
            metrics.update({
                "train_time_ms": train_time,
                "n_train": len(X_train),
                "n_test": len(X_test),
            })
            baseline_metrics_list.append(metrics)

            # Raw result
            raw = {
                "repeat": repeat,
                "seed": seed,
                "configuration": {"config": baseline_config, "type": "baseline"},
                "metrics": metrics,
            }
            baseline_raw_list.append(raw)

        # === Alternative Run (with perturbation) ===
        alternative_metrics_list: List[Dict[str, Any]] = []
        alternative_raw_list: List[Any] = []

        perturbation_type = perturbation_config.get("perturbation_type", "gaussian_noise")
        perturbation_strength = perturbation_config.get("perturbation_strength", 0.1)

        for repeat in range(max(1, n_repeats)):
            seed = experiment.random_seed + (repeat + 100) * 1000
            rng = np.random.RandomState(seed)

            # Apply perturbation to alternative data
            df = alternative_df.dropna().reset_index(drop=True)
            if perturbation_type == "gaussian_noise":
                noise = rng.normal(0, perturbation_strength, df[feature_cols].shape)
                perturbed_features = df[feature_cols].values + noise
            elif perturbation_type == "feature_dropout":
                mask = rng.random(df[feature_cols].shape) > perturbation_strength
                perturbed_features = df[feature_cols].values * mask
            else:
                perturbed_features = df[feature_cols].values

            y = df["label"].values
            X_train, X_test, y_train, y_test = train_test_split(
                perturbed_features, y, test_size=0.25, random_state=seed, stratify=y
            )

            model = RandomForestClassifier(
                n_estimators=50, max_depth=8, random_state=seed
            )
            t0 = time.perf_counter()
            model.fit(X_train, y_train)
            train_time = (time.perf_counter() - t0) * 1000

            # Evaluate alternative/perturbed
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)[:, 1]
            metrics = classification_metrics(y_test, y_pred, y_prob)
            metrics.update({
                "train_time_ms": train_time,
                "n_train": len(X_train),
                "n_test": len(X_test),
            })
            alternative_metrics_list.append(metrics)

            raw = {
                "repeat": repeat,
                "seed": seed,
                "configuration": {"config": alternative_config, "type": "alternative_perturbed"},
                "perturbation_type": perturbation_type,
                "perturbation_strength": perturbation_strength,
                "metrics": metrics,
            }
            alternative_raw_list.append(raw)

        # === Statistical Analysis ===
        # The groups use different seeds and may use different data/perturbations,
        # so they are not matched pairs.
        baseline_f1s = [m.get("f1", 0) for m in baseline_metrics_list]
        alternative_f1s = [m.get("f1", 0) for m in alternative_metrics_list]
        baseline_trial_ids = [
            f"baseline-seed-{run['seed']}" for run in baseline_raw_list
        ]
        alternative_trial_ids = [
            f"alternative-seed-{run['seed']}" for run in alternative_raw_list
        ]
        statistical_analysis = independent_bootstrap_comparison(
            baseline_f1s,
            alternative_f1s,
            baseline_trial_ids,
            alternative_trial_ids,
            baseline_raw_data_ref="/raw_results/baseline",
            treatment_raw_data_ref="/raw_results/alternative_perturbed",
            seed=experiment.random_seed,
        )
        baseline_f1_mean = float(np.mean(baseline_f1s)) if baseline_f1s else 0.0
        alternative_f1_mean = (
            float(np.mean(alternative_f1s)) if alternative_f1s else 0.0
        )
        f1_drop = round(baseline_f1_mean - alternative_f1_mean, 4)
        difference_ci = statistical_analysis["confidence_interval"]
        f1_drop_ci = (
            {
                "low": -difference_ci["high"],
                "high": -difference_ci["low"],
            }
            if difference_ci
            else None
        )

        # === Conclusion Determination ===
        conclusion_status: Optional[str] = "INCONCLUSIVE"
        justification_parts: List[str] = []

        if f1_drop_ci and f1_drop_ci["low"] > 0.15:
            conclusion_status = "NOT_SUPPORTED"
            justification_parts.append(
                f"The independent-trial 95% bootstrap interval for F1 drop "
                f"({f1_drop_ci['low']:.4f}, {f1_drop_ci['high']:.4f}) exceeds "
                "the 0.15 practical-drop threshold."
            )
        elif f1_drop_ci and f1_drop_ci["low"] > 0.05:
            conclusion_status = "PARTIALLY_SUPPORTED"
            justification_parts.append(
                f"The independent-trial 95% bootstrap interval for F1 drop "
                f"({f1_drop_ci['low']:.4f}, {f1_drop_ci['high']:.4f}) exceeds "
                "the 0.05 practical-drop threshold, but not 0.15."
            )
        else:
            justification_parts.append(
                "The interval does not establish either practical-drop threshold, "
                "or too few trial units were available; no significance claim is made."
            )

        justification = " | ".join(justification_parts)

        # === Provenance ===
        provenance = {
            "experiment_id": experiment.id,
            "claim_id": claim_id,
            "claim_statement": claim_statement,
            "baseline_configuration": baseline_config,
            "alternative_configuration": alternative_config,
            "perturbation_config": perturbation_config,
            "datasets": {
                "baseline": baseline_provenance,
                "alternative": alternative_provenance,
            },
            "random_seed": experiment.random_seed,
            "n_repeats": n_repeats,
            "perturbation_type": perturbation_type,
            "perturbation_strength": perturbation_strength,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # === Configuration Hash ===
        config_payload = {
            "experiment_id": experiment.id,
            "claim_id": claim_id,
            "baseline_configuration": baseline_config,
            "alternative_configuration": alternative_config,
            "perturbation_config": perturbation_config,
        }
        configuration_hash = sha256_hash(canonicalize(config_payload))

        # === Build Result ===
        result = {
            "experiment_id": experiment.id,
            "claim_id": claim_id,
            "claim_statement": claim_statement,

            # Configuration
            "configuration": {
                "baseline_configuration": baseline_config,
                "alternative_configuration": alternative_config,
                "perturbation_type": perturbation_type,
                "perturbation_strength": perturbation_strength,
                "n_repeats": n_repeats,
                "random_seed": experiment.random_seed,
            },

            # Provenance
            "provenance": provenance,

            # Raw results
            "raw_results": {
                "baseline": baseline_raw_list,
                "alternative_perturbed": alternative_raw_list,
            },

            # Derived metrics
            "derived_metrics": {
                "baseline": {
                    "f1_mean": round(baseline_f1_mean, 4),
                    "f1_series": [round(v, 4) for v in baseline_f1s],
                },
                "alternative": {
                    "f1_mean": round(alternative_f1_mean, 4),
                    "f1_series": [round(v, 4) for v in alternative_f1s],
                },
                "difference": {
                    "f1_drop": f1_drop,
                    "f1_drop_confidence_interval": f1_drop_ci,
                    "cohens_d": statistical_analysis["cohens_d"],
                    "effect_size_method": statistical_analysis["effect_size_method"],
                    "statistical_analysis": statistical_analysis,
                },
                "conclusion": {
                    "status": conclusion_status,
                    "justification": justification,
                    "conclusion_status": conclusion_status,
                    "conclusion_labels": {
                        "SUPPORTED": "SUPPORTED",
                        "PARTIALLY_SUPPORTED": "PARTIALLY_SUPPORTED",
                        "NOT_SUPPORTED": "NOT_SUPPORTED",
                        "INCONCLUSIVE": "INCONCLUSIVE",
                    },
                },
            },

            # Plots (file paths - generated separately or referenced)
            "plots": {
                "f1_comparison": f"falsification_{experiment.id}_f1_comparison.png",
                "perturbation_analysis": f"falsification_{experiment.id}_perturbation_analysis.png",
                "distribution_comparison": f"falsification_{experiment.id}_distribution_comparison.png",
            },

            # Evidence
            "evidence": {
                "claim_id": claim_id,
                "conclusion_status": conclusion_status,
                "configuration_hash": configuration_hash,
                "provenance": provenance,
                "raw_result_files": [],
                "derivation_method": "independent_trial_percentile_bootstrap_cohens_d",
                "statistical_raw_data_refs": statistical_analysis["raw_data_refs"],
                "statistical_raw_data_sha256": statistical_analysis["raw_data_sha256"],
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },

            # Status
            "status": "COMPLETED",
            "execution_time_s": round(time.perf_counter() - experiment_started, 2),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # Calculate result hash (without envelope keys)
        result_hash = sha256_hash(canonicalize(_deterministic_metrics(result.get("derived_metrics", {}))))

        result["result_hash"] = result_hash

        # Persist to database
        falsification_result = FalsificationResult(
            experiment_id=experiment.id,
            run_index=0,
            configuration_snapshot=json.dumps(baseline_config),
            raw_data=json.dumps(result["raw_results"]),
            derived_metrics=json.dumps(result["derived_metrics"]),
            statistical_test="independent_trial_percentile_bootstrap",
            statistical_result=json.dumps(statistical_analysis),
            plots=json.dumps(result["plots"]),
            evidence_summary=json.dumps(result["evidence"]),
            conclusion_status=conclusion_status,
            conclusion_justification=justification,
            reproducibility_metadata=json.dumps(provenance),
            execution_time_s=result.get("execution_time_s", 0.0),
        )

        session.add(falsification_result)
        session.commit()
        session.refresh(falsification_result)

        # Update experiment conclusion
        experiment.conclusion_status = conclusion_status
        experiment.configuration_hash = configuration_hash
        experiment.result_hash = result_hash
        experiment.status = "completed"
        session.commit()

        result["persisted_result_id"] = falsification_result.id
        return result

    finally:
        if owns_session:
            session.close()


def run_falsification_with_claim(
    claim_id: str,
    baseline_config: Dict[str, Any],
    alternative_config: Dict[str, Any],
    perturbation_config: Dict[str, Any],
    n_repeats: int = 3,
    db=None,
) -> Dict[str, Any]:
    """Run a falsification experiment by claim_id (frontend-friendly wrapper)."""

    # Find or create the experiment
    session = db or SessionLocal()
    owns_session = db is None

    try:
        experiment = (
            session.query(FalsificationExperiment)
            .filter(FalsificationExperiment.claim_id == claim_id)
            .first()
        )

        if not experiment:
            # Create a new experiment entry for this claim
            experiment = FalsificationExperiment(
                name=claim_id,
                claim_id=claim_id,
                claim_statement=baseline_config.get("claim_statement", "Unnamed claim"),
                baseline_configuration=json.dumps(baseline_config),
                alternative_configuration=json.dumps(alternative_config),
                n_repeats=n_repeats,
                random_seed=baseline_config.get("random_state", 42),
                status="pending",
            )
            session.add(experiment)
            session.commit()
            session.refresh(experiment)

        return run_falsification_experiment(
            experiment_id=experiment.id,
            baseline_config=baseline_config,
            alternative_config=alternative_config,
            perturbation_config=perturbation_config,
            n_repeats=n_repeats,
            db=session if not owns_session else None,
        )
    finally:
        if owns_session:
            session.close()