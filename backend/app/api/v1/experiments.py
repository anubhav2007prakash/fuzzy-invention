"""Experiment endpoints for SentinelCrypt AI research benchmark suite."""
from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.services.experiment_service import (
    ExperimentService,
    KNOWN_EXPERIMENT_IDS,
    result_artifact_name,
)

router = APIRouter()


def _normalize(exp_id: str) -> str:
    """Validate an experiment id against the core set or a registered plugin."""
    normalized = exp_id.upper().strip()
    if normalized in KNOWN_EXPERIMENT_IDS or result_artifact_name(normalized):
        return normalized
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(f"Experiment '{exp_id}' not recognized. "
                f"Supported: {', '.join(KNOWN_EXPERIMENT_IDS)} "
                "(plus registered experiment plugins)."),
    )


@router.get(
    "",
    summary="List all research experiments and latest execution status",
    response_model=Dict[str, Any],
)
def list_experiments(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve all 4 benchmark research experiments (EXP-A, EXP-B, EXP-C, EXP-D)."""
    service = ExperimentService(db)
    experiments = service.list_experiments()
    return {
        "experiments": experiments,
        "total": len(experiments),
    }


@router.get(
    "/presentation-summary",
    summary="Get professor-mode research presentation summary",
    response_model=Dict[str, Any],
)
def get_presentation_summary(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate the current research pipeline, latest results, limitations, and future work."""
    service = ExperimentService(db)
    return service.build_presentation_summary()


@router.post(
    "/{exp_id}/reproducibility-package",
    summary="Export the full one-click reproducibility package",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
)
def export_reproducibility_package(
    exp_id: str,
    config: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Produce README, config.yaml, manifests, metrics.csv, plots/, evidence/,
    verification report, and reproduction instructions for one experiment."""
    normalized = _normalize(exp_id)
    service = ExperimentService(db)
    try:
        result = (
            service.run_experiment_by_id(normalized, config=config)
            if config else service.get_experiment_by_id(normalized)
        )
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Experiment '{exp_id}' has no result to package.",
            )
        from backend.app.research.reproducibility import export_reproducibility_package
        normalized_config = service.validate_experiment_config(
            normalized, config or result.get("parameters") or {}
        )
        return export_reproducibility_package(normalized, result, normalized_config)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reproducibility package export failed for '{exp_id}': {str(e)}",
        )


@router.get(
    "/{exp_id}/trust-checklist",
    summary="Structured trust evidence checklist for an experiment result",
    response_model=Dict[str, Any],
)
def get_trust_checklist(exp_id: str) -> Dict[str, Any]:
    """Transparent evidence checklist (not a numeric trust score)."""
    _normalize(exp_id)
    from backend.app.research.provenance import experiment_trust_checklist
    try:
        return experiment_trust_checklist(exp_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{exp_id}",
    summary="Get details and results of a specific experiment",
    response_model=Dict[str, Any],
)
def get_experiment(
    exp_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Fetch stored results or trigger on-demand run of any registered experiment."""
    normalized = _normalize(exp_id)

    service = ExperimentService(db)
    try:
        res = service.get_experiment_by_id(normalized)
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Experiment '{exp_id}' result not found.",
            )
        return res
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Experiment execution failed: {str(e)}",
        )


@router.post(
    "/{exp_id}/run",
    summary="Trigger live execution of a research experiment",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
)
def run_experiment(
    exp_id: str,
    config: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Execute any registered experiment runner and persist output to results/."""
    normalized = _normalize(exp_id)

    service = ExperimentService(db)
    try:
        return service.run_experiment_by_id(normalized, config=config)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Experiment '{exp_id}' failed during execution: {str(e)}",
        )


@router.post(
    "/{exp_id}/evidence",
    summary="Export a portable research evidence package",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
)
def export_experiment_evidence(
    exp_id: str,
    config: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Export structured research evidence files for an experiment."""
    _normalize(exp_id)
    service = ExperimentService(db)
    try:
        return service.export_evidence_package(exp_id, config=config)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evidence export failed for experiment '{exp_id}': {str(e)}",
        )

