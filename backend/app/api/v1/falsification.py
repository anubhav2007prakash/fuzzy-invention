"""Falsification Lab API endpoints for SentinelCrypt AI research."""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.services.experiment_service import ExperimentService
from backend.app.db.models import FalsificationExperiment, FalsificationResult
from backend.app.research.falsification import (
    run_falsification_experiment,
    run_falsification_with_claim,
    CONCLUSION_STATUSES,
)

router = APIRouter()


def _normalize_claim_id(claim_id: str) -> str:
    """Normalize a claim ID for lookup."""
    normalized = claim_id.strip().upper()
    return normalized


@router.post(
    "/claims",
    summary="Create a new falsification claim",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
)
def create_claim(
    claim_id: str,
    claim_statement: str,
    baseline_configuration: Dict[str, Any],
    alternative_configuration: Dict[str, Any],
    perturbation_configuration: Dict[str, Any],
    alternative_dataset_id: Optional[str] = None,
    n_repeats: int = 3,
    random_seed: int = 42,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Define a new research claim to attempt to disprove.

    Args:
        claim_id: Unique identifier for the claim (e.g., "CLAIM-001")
        claim_statement: Human-readable description of the research claim
        baseline_configuration: Configuration for the baseline model/dataset
        alternative_configuration: Configuration for the alternative model/dataset
        perturbation_configuration: Controlled perturbation parameters
        alternative_dataset_id: Optional FK to a different dataset for comparison
        n_repeats: Number of repeated runs for statistical robustness
        random_seed: Base random seed for reproducibility

    Returns:
        Created claim metadata with experiment ID
    """
    session = db
    try:
        # Check if claim already exists
        existing = (
            session.query(FalsificationExperiment)
            .filter(FalsificationExperiment.claim_id == claim_id.upper())
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Claim '{claim_id}' already exists.",
            )

        experiment = FalsificationExperiment(
            claim_id=claim_id.upper(),
            claim_statement=claim_statement,
            baseline_configuration=json.dumps(baseline_configuration),
            alternative_configuration=json.dumps(alternative_configuration),
            alternative_dataset_id=alternative_dataset_id,
            n_repeats=n_repeats,
            random_seed=random_seed,
            status="pending",
        )

        session.add(experiment)
        session.commit()
        session.refresh(experiment)

        return {
            "experiment_id": experiment.id,
            "claim_id": experiment.claim_id,
            "claim_statement": experiment.claim_statement,
            "status": experiment.status,
            "created_at": str(experiment.created_at),
        }
    finally:
        session.close()


@router.get(
    "/claims",
    summary="List all falsification claims",
    response_model=Dict[str, Any],
)
def list_claims(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all registered falsification claims/experiments."""
    experiments = (
        session.query(FalsificationExperiment)
        .order_by(FalsificationExperiment.created_at.desc())
        .all()
    )
    return {
        "experiments": [
            {
                "id": exp.id,
                "claim_id": exp.claim_id,
                "claim_statement": exp.claim_statement,
                "baseline_configuration": json.loads(exp.baseline_configuration) if exp.baseline_configuration else {},
                "alternative_configuration": json.loads(exp.alternative_configuration) if exp.alternative_configuration else {},
                "alternative_dataset_id": exp.alternative_dataset_id,
                "n_repeats": exp.n_repeats,
                "random_seed": exp.random_seed,
                "status": exp.status,
                "conclusion_status": exp.conclusion_status,
                "created_at": str(exp.created_at),
            }
            for exp in experiments
        ],
        "total": len(experiments),
    }


@router.get(
    "/claims/{claim_id}",
    summary="Get a specific falsification claim details",
    response_model=Dict[str, Any],
)
def get_claim(
    claim_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve details of a specific falsification claim."""
    experiment = (
        session.query(FalsificationExperiment)
        .filter(FalsificationExperiment.claim_id == claim_id.upper())
        .first()
    )
    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Falsification claim '{claim_id}' not found.",
        )

    # Load any existing results
    results = (
        session.query(FalsificationResult)
        .filter(FalsificationResult.experiment_id == experiment.id)
        .all()
    )

    return {
        "experiment": {
            "id": experiment.id,
            "claim_id": experiment.claim_id,
            "claim_statement": experiment.claim_statement,
            "description": experiment.description,
            "baseline_configuration": json.loads(experiment.baseline_configuration) if experiment.baseline_configuration else {},
            "alternative_configuration": json.loads(experiment.alternative_configuration) if experiment.alternative_configuration else {},
            "alternative_dataset_id": experiment.alternative_dataset_id,
            "perturbation_type": experiment.perturbation_type,
            "perturbation_strength": experiment.perturbation_strength,
            "n_repeats": experiment.n_repeats,
            "random_seed": experiment.random_seed,
            "acceptance_criteria": json.loads(experiment.acceptance_criteria) if experiment.acceptance_criteria else None,
            "conclusion_status": experiment.conclusion_status,
            "status": experiment.status,
            "created_at": str(experiment.created_at),
            "updated_at": str(experiment.updated_at),
        },
        "results": [
            {
                "run_index": r.run_index,
                "conclusion_status": r.conclusion_status,
                "conclusion_justification": r.conclusion_justification,
                "derived_metrics": json.loads(r.derived_metrics) if r.derived_metrics else {},
                "statistical_test": r.statistical_test,
                "statistical_result": json.loads(r.statistical_result) if r.statistical_result else {},
                "created_at": str(r.created_at),
            }
            for r in results
        ],
    }


@router.post(
    "/claims/{claim_id}/run",
    summary="Execute falsification experiment for a claim",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
)
def run_claim_experiment(
    claim_id: str,
    config: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Execute a full falsification experiment for the given claim.

    Runs the comparison between baseline and alternative configurations
    with controlled perturbation and repeated runs, producing statistical
    analysis and a conclusion status.

    Args:
        claim_id: The claim identifier
        config: Optional override configuration (baseline, alternative, perturbation)

    Returns:
        Complete falsification experiment result
    """
    normalized_claim = claim_id.upper().strip()

    # Find or create the experiment
    experiment = (
        db.query(FalsificationExperiment)
        .filter(FalsificationExperiment.claim_id == normalized_claim)
        .first()
    ) if db else None

    session = db or SessionLocal()
    owns_session = db is None

    try:
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Falsification claim '{claim_id}' not found. Create it first using POST /api/v1/claims.",
            )

        # Use provided config or experiment stored config
        if config is None:
            config = {
                "baseline_configuration": json.loads(experiment.baseline_configuration) if experiment.baseline_configuration else {},
                "alternative_configuration": json.loads(experiment.alternative_configuration) if experiment.alternative_configuration else {},
                "perturbation_configuration": {
                    "perturbation_type": experiment.perturbation_type or "gaussian_noise",
                    "perturbation_strength": experiment.perturbation_strength or 0.1,
                },
            }

        result = run_falsification_with_claim(
            claim_id=normalized_claim,
            baseline_config=config.get("baseline_configuration", {}),
            alternative_config=config.get("alternative_configuration", {}),
            perturbation_config=config.get("perturbation_configuration", {}),
            n_repeats=experiment.n_repeats,
            db=session if not owns_session else None,
        )

        # Mark experiment as completed with conclusion
        experiment.conclusion_status = result.get("derived_metrics", {}).get(
            "conclusion", {}
        ).get("status", "INCONCLUSIVE")
        experiment.status = "completed"
        session.commit()

        return result
    finally:
        if owns_session:
            session.close()


@router.post(
    "/claims/{claim_id}/acceptance-criteria",
    summary="Set acceptance criteria for a claim",
    response_model=Dict[str, Any],
)
def set_acceptance_criteria(
    claim_id: str,
    criteria: Dict[str, Any],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Define acceptance criteria for claim verification.

    Args:
        claim_id: The claim identifier
        criteria: Dictionary of practical acceptance criteria (for example, an F1-drop threshold)

    Returns:
        Updated experiment with acceptance criteria
    """
    normalized_claim = claim_id.upper().strip()
    experiment = (
        session.query(FalsificationExperiment)
        .filter(FalsificationExperiment.claim_id == normalized_claim)
        .first()
    ) if (session := db) else None

    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Falsification claim '{claim_id}' not found.",
        )

    experiment.acceptance_criteria = json.dumps(criteria)
    session.commit()

    return {
        "claim_id": experiment.claim_id,
        "acceptance_criteria": criteria,
        "updated_at": str(experiment.updated_at),
    }


@router.get(
    "/conclusion-statuses",
    summary="Get valid conclusion status values",
    response_model=Dict[str, Any],
)
def get_conclusion_statuses(
) -> Dict[str, Any]:
    """Return the valid conclusion status values for falsification experiments."""
    return {
        "statuses": CONCLUSION_STATUSES,
        "descriptions": {
            "SUPPORTED": "Claim is supported - perturbation did not significantly degrade performance",
            "PARTIALLY_SUPPORTED": "Claim is partially supported - perturbation caused moderate degradation",
            "NOT_SUPPORTED": "Claim is not supported - perturbation significantly degraded performance (statistically)",
            "INCONCLUSIVE": "Claim is inconclusive - insufficient evidence to support or refute",
        },
    }