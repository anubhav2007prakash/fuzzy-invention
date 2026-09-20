"""FastAPI application factory for SentinelCrypt AI."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.core.exceptions import SentinelCryptException
from backend.app.core.logging import get_logger
from backend.app.db.database import init_db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB tables. Shutdown: nothing required."""
    logger.info("Starting %s …", settings.PROJECT_NAME)
    init_db()
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

# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(SentinelCryptException)
async def sentinelcrypt_exception_handler(request: Request, exc: SentinelCryptException):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": exc.code, "message": exc.message, "details": {}}},
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
