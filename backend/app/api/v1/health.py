"""Health check endpoints — /api/v1/health."""
import os
import platform
import sys
import time
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.database import get_db

router = APIRouter()

_start_time = time.time()


@router.get("", summary="Service health check", tags=["health"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "api_version": "v1",
    }


@router.get("/detailed", summary="Detailed health check with DB, disk, and version info")
def health_check_detailed(db: Session = Depends(get_db)):
    """Comprehensive health check reporting DB connectivity, Alembic version,
    disk usage, and component counts."""
    result = {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "api_version": "v1",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }

    # Database connectivity
    try:
        db.execute(text("SELECT 1"))
        result["database"] = {"status": "connected", "url": settings.DATABASE_URL.split("/")[-1]}
    except Exception as e:
        result["database"] = {"status": "error", "error": str(e)}
        result["status"] = "degraded"

    # Alembic version
    try:
        rows = db.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        result["alembic_version"] = rows[0][0] if rows else "none"
    except Exception:
        result["alembic_version"] = "unknown"

    # Component counts
    try:
        for table in ["datasets", "models", "predictions", "explanations", "audit_records"]:
            count = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            result[f"{table}_count"] = count
    except Exception:
        pass

    # Disk usage for data directories
    for name, path in [("data_raw", settings.DATA_RAW_DIR), ("models_trained", settings.MODELS_TRAINED_DIR)]:
        try:
            size = sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file())
            result[f"disk_{name}_bytes"] = size
        except Exception:
            result[f"disk_{name}_bytes"] = -1

    return result
