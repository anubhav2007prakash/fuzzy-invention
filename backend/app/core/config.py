"""Application configuration — loaded from environment or .env file."""
from pathlib import Path
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings

# Repository root (two levels up from backend/app/core/)
_REPO_ROOT = Path(__file__).resolve().parents[4]

class Settings(BaseSettings):
    PROJECT_NAME: str = "SentinelCrypt AI"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "default-secret-key-change-in-production"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # Database (SQLite default, swap to PostgreSQL via .env)
    DATABASE_URL: str = f"sqlite:///{_REPO_ROOT / 'sentinelcrypt.db'}"

    # Data storage paths
    DATA_RAW_DIR: Path = _REPO_ROOT / "data" / "raw"
    DATA_PROCESSED_DIR: Path = _REPO_ROOT / "data" / "processed"
    MODELS_TRAINED_DIR: Path = _REPO_ROOT / "models" / "trained"
    MODELS_ARTIFACTS_DIR: Path = _REPO_ROOT / "models" / "artifacts"
    RESULTS_DIR: Path = _REPO_ROOT / "results"

    # ML defaults (fixed seed for reproducibility)
    RANDOM_SEED: int = 42
    TRAIN_RATIO: float = 0.8

    # Maximum file size for dataset uploads (bytes) — 500 MB
    MAX_UPLOAD_SIZE_BYTES: int = 500 * 1024 * 1024

    @field_validator("DATA_RAW_DIR", "DATA_PROCESSED_DIR", "MODELS_TRAINED_DIR",
                     "MODELS_ARTIFACTS_DIR", "RESULTS_DIR", mode="before")
    @classmethod
    def ensure_dir(cls, v):
        p = Path(v)
        p.mkdir(parents=True, exist_ok=True)
        return p

    model_config = {"case_sensitive": True, "env_file": ".env"}


settings = Settings()
