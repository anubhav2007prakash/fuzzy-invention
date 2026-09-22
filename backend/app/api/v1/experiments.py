"""Experiment endpoints for SentinelCrypt AI research benchmark suite."""
from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.services.experiment_service import ExperimentService

router = APIRouter()


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


@router.get(
    "/{exp_id}",
    summary="Get details and results of a specific experiment",
    response_model=Dict[str, Any],
)
def get_experiment(
    exp_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Fetch stored results or trigger on-demand run of EXP-A, EXP-B, EXP-C, or EXP-D."""
    normalized = exp_id.upper().strip()
    if normalized not in ("EXP-A", "EXP-B", "EXP-C", "EXP-D"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Experiment '{exp_id}' not recognized. Supported: EXP-A, EXP-B, EXP-C, EXP-D.",
        )

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
    """Execute experiment runner (EXP-A, EXP-B, EXP-C, or EXP-D) and persist scientific output to results/."""
    normalized = exp_id.upper().strip()
    if normalized not in ("EXP-A", "EXP-B", "EXP-C", "EXP-D"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown experiment ID '{exp_id}'. Supported: EXP-A, EXP-B, EXP-C, EXP-D.",
        )

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

