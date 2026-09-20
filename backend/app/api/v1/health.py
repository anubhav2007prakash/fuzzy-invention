"""Health check endpoint — /api/v1/health."""
from fastapi import APIRouter
from backend.app.core.config import settings

router = APIRouter()

@router.get("", summary="Service health check", tags=["health"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "api_version": "v1",
    }
