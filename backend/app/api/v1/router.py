"""API v1 root router — registers all sub-routers."""
from fastapi import APIRouter
from backend.app.api.v1 import (
    health, datasets, models, predictions, explanations, audit, experiments,
    benchmark, research, collaboration, falsification, integrity,
)

api_router = APIRouter()

api_router.include_router(health.router,       prefix="/health",       tags=["Health"])
api_router.include_router(datasets.router,     prefix="/datasets",     tags=["Datasets"])
api_router.include_router(models.router,       prefix="/models",       tags=["Models"])
api_router.include_router(predictions.router,  prefix="/predictions",  tags=["Predictions"])
api_router.include_router(explanations.router, prefix="/explanations", tags=["Explainability"])
api_router.include_router(audit.router,        prefix="/audit",        tags=["Audit Ledger"])
api_router.include_router(experiments.router,  prefix="/experiments",  tags=["Experiments"])
api_router.include_router(benchmark.router,    prefix="/benchmark",    tags=["Benchmark"])
api_router.include_router(research.router,     prefix="/research",     tags=["Research"])
api_router.include_router(collaboration.router, prefix="/collaboration", tags=["Collaboration & Review"])
api_router.include_router(falsification.router,  prefix="/falsification", tags=["Falsification Lab"])
api_router.include_router(integrity.router,  prefix="/integrity", tags=["Database Integrity"])
