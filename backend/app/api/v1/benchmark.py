"""Benchmark endpoints (items: standard benchmark, pipeline timing, scalability, leaderboard)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.database import get_db

router = APIRouter()


@router.post(
    "/run",
    summary="Run the standardized benchmark across data sources",
    response_model=Dict[str, Any],
)
def run_benchmark(
    config: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Execute the full benchmark protocol (F1/macro-F1/PR-AUC/latency/memory/
    stability/calibration/OOD/ledger overhead/reproducibility) and write the report."""
    from backend.app.research.benchmark import run_benchmark as _run

    cfg = config or {}
    try:
        return _run(
            sources=cfg.get("sources"),
            n_samples=int(cfg.get("n_samples", 1200)),
            seed=int(cfg.get("seed", cfg.get("random_state", 42))),
            repeats=int(cfg.get("repeats", 2)),
            dataset_id=cfg.get("dataset_id"),
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Benchmark execution failed: {str(e)}",
        )


@router.get(
    "/report",
    summary="Get the latest machine-generated benchmark report",
    response_model=Dict[str, Any],
)
def latest_report() -> Dict[str, Any]:
    from backend.app.research.benchmark import latest_report as _latest

    report = _latest()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No benchmark report yet — POST /benchmark/run first.",
        )
    return report


@router.get(
    "/sources",
    summary="List benchmark data sources and their provenance labels",
    response_model=Dict[str, Any],
)
def list_sources() -> Dict[str, Any]:
    from backend.app.research.benchmark import BENCHMARK_SOURCES

    return {
        "sources": [
            {"key": key, **spec} for key, spec in BENCHMARK_SOURCES.items()
        ],
        "note": (
            "UNSW-NB15 and CICIDS2017 run on distribution-matched synthetic proxies "
            "(labelled `synthetic_proxy`) until real captures are registered via the "
            "Datasets API (pass dataset_id to run the protocol on them)."
        ),
    }


@router.post(
    "/pipeline",
    summary="Benchmark every pipeline stage (end-to-end latency breakdown)",
    response_model=Dict[str, Any],
)
def run_pipeline(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Ingestion → preprocessing → prediction → SHAP → evidence → ledger → verification."""
    from backend.app.research.benchmark import run_pipeline_benchmark

    cfg = config or {}
    try:
        return run_pipeline_benchmark(
            n_samples=int(cfg.get("n_samples", 600)),
            seed=int(cfg.get("seed", cfg.get("random_state", 42))),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/scalability",
    summary="Run the scalability sweep across increasing data sizes",
    response_model=Dict[str, Any],
)
def run_scalability(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """10K → 1M rows: training time, throughput, memory, explanation, ledger, DB size."""
    from backend.app.research.benchmark import run_scalability as _run

    cfg = config or {}
    try:
        return _run(
            sizes=cfg.get("sizes"),
            seed=int(cfg.get("seed", cfg.get("random_state", 42))),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/leaderboard",
    summary="Transparent experimental table across all stored results",
    response_model=Dict[str, Any],
)
def leaderboard(
    dataset: Optional[str] = Query(None, description="Filter by dataset substring"),
    model: Optional[str] = Query(None, description="Filter by model substring"),
    experiment: Optional[str] = Query(None, description="Filter by experiment id"),
) -> Dict[str, Any]:
    from backend.app.research.benchmark import leaderboard as _board

    return _board(
        dataset_filter=dataset,
        model_filter=model,
        experiment_filter=experiment,
    )
