"""Application configuration — loaded from environment or .env file.

Validation rules are enforced at import time.  Dangerous defaults are
rejected when ENVIRONMENT is not 'development'.
"""
import warnings
from pathlib import Path
from typing import List, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

# Repository root (three levels up from backend/app/core/)
_REPO_ROOT = Path(__file__).resolve().parents[3]


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

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        """Enforce environment-specific validation rules."""
        env = self.ENVIRONMENT.lower()

        # Reject dangerous defaults in non-development environments
        if env in ("production", "staging"):
            if self.SECRET_KEY == "default-secret-key-change-in-production":
                raise ValueError(
                    "SECRET_KEY must be changed from the default in production/staging. "
                    "Set the SECRET_KEY environment variable."
                )
            if "sqlite" in self.DATABASE_URL.lower():
                warnings.warn(
                    "SQLite is used in a non-development environment. "
                    "Consider switching to PostgreSQL for production.",
                    UserWarning,
                    stacklevel=2,
                )

        # Validate train_ratio
        if not (0.1 <= self.TRAIN_RATIO <= 0.95):
            raise ValueError(
                f"TRAIN_RATIO must be between 0.1 and 0.95, got {self.TRAIN_RATIO}"
            )

        # Validate upload size
        if self.MAX_UPLOAD_SIZE_BYTES < 1024:
            raise ValueError(
                "MAX_UPLOAD_SIZE_BYTES must be at least 1024 bytes."
            )

        # Validate log level
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.LOG_LEVEL.upper() not in valid_log_levels:
            raise ValueError(
                f"LOG_LEVEL must be one of {valid_log_levels}, got '{self.LOG_LEVEL}'"
            )

        return self

    model_config = {"case_sensitive": True, "env_file": ".env"}


settings = Settings()
