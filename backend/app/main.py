"""FastAPI application factory for SentinelCrypt AI."""
from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, Request
from fastapi.exceptions import ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sqlalchemy.exc import SQLAlchemyError

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.core.exceptions import DatabaseUnavailableError, SentinelCryptException
from backend.app.core.logging import get_logger
from backend.app.db.database import init_db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB tables. Shutdown: nothing required."""
    logger.info("Starting %s …", settings.PROJECT_NAME)
    init_db()
    from backend.app.plugins import get_registry

    logger.info("Research plugins: %s", get_registry().counts())
    logger.info("Database tables initialised.")
    yield
    logger.info("%s shutting down.", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Verifiable Machine Learning & Cryptographic Audit Ledger "
        "for Network Intrusion Detection Systems (NIDS). "
        "Research prototype — not a production security product."
    ),
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Demo Mode read-only guard (public research demo) ─────────────────────────
@app.middleware("http")
async def demo_mode_guard(request: Request, call_next):
    """In Demo Mode, reject mutating endpoints (no uploads/training/runs)."""
    from backend.app.research.modes import endpoint_allowed

    if not endpoint_allowed(request.method, request.url.path):
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "DEMO_MODE_READ_ONLY",
                    "message": (
                        "Application is in Demo Mode (read-only). "
                        "Switch to Research Mode via POST /api/v1/research/mode."
                    ),
                    "details": {"mode": "demo", "method": request.method,
                                "path": request.url.path},
                }
            },
        )
    return await call_next(request)


# ── Global exception handlers ──────────────────────────────────────────────
@app.exception_handler(SentinelCryptException)
async def sentinelcrypt_exception_handler(request: Request, exc: SentinelCryptException):
    status_code = 503 if isinstance(exc, DatabaseUnavailableError) else 422
    return JSONResponse(
        status_code=status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    logger.error("Database operational error during request to %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "DATABASE_UNAVAILABLE",
                "message": "Database service is currently unavailable or encountered an operational error.",
                "details": {"type": exc.__class__.__name__},
            }
        },
    )


@app.exception_handler(ResponseValidationError)
async def response_validation_error_handler(
    request: Request,
    exc: ResponseValidationError,
):
    logger.error(
        "API response validation failed for %s",
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INVALID_SERVER_RESPONSE",
                "message": "The server generated a response that does not match its API schema.",
                "details": {},
            }
        },
    )


@app.exception_handler(ValueError)
async def validation_error_handler(request: Request, exc: ValueError):
    """Catch UUID validation errors and return consistent format."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": str(exc),
                "details": {},
            }
        },
    )


@app.exception_handler(TypeError)
@app.exception_handler(json.JSONDecodeError)
async def serialization_error_handler(request: Request, exc: Exception):
    """Malformed/unserializable input (NaN/Infinity, bad types, broken JSON
    escaping) must surface as 422, never a raw 500 — the API is an attack
    surface and crash responses leak stack semantics.  Regression-tested in
    tests/unit/test_security_redteam.py (NaN body → 422, not 500)."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "MALFORMED_INPUT",
                "message": "Request body could not be processed (unserializable or malformed value).",
                "details": {"type": exc.__class__.__name__},
            }
        },
    )

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
def root():
    return {
        "service": settings.PROJECT_NAME,
        "docs": "/docs",
        "api": settings.API_V1_STR,
    }
