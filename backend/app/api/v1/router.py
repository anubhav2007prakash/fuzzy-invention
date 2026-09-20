"""API v1 root router — registers all sub-routers."""
from fastapi import APIRouter
from backend.app.api.v1 import health, datasets, models, predictions, explanations, audit, experiments

api_router = APIRouter()

api_router.include_router(health.router,       prefix="/health",       tags=["Health"])
api_router.include_router(datasets.router,     prefix="/datasets",     tags=["Datasets"])
api_router.include_router(models.router,       prefix="/models",       tags=["Models"])
api_router.include_router(predictions.router,  prefix="/predictions",  tags=["Predictions"])
api_router.include_router(explanations.router, prefix="/explanations", tags=["Explainability"])
api_router.include_router(audit.router,        prefix="/audit",        tags=["Audit Ledger"])
api_router.include_router(experiments.router,  prefix="/experiments",  tags=["Experiments"])
