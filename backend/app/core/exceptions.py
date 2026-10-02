"""Structured application exceptions for SentinelCrypt AI."""

import re

# UUID format: 8-4-4-4-12 hex characters
_UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


def validate_uuid_format(resource_id: str, resource_type: str = "resource") -> str:
    """Validate that a resource ID is a valid UUID format.

    Args:
        resource_id: The ID string to validate.
        resource_type: Human-readable name for error messages.

    Returns:
        The validated resource_id.

    Raises:
        ValueError: If the ID is not a valid UUID.
    """
    if not resource_id or not isinstance(resource_id, str):
        raise ValueError(f"Invalid {resource_type} ID: empty or not a string.")
    if not _UUID_PATTERN.match(resource_id):
        raise ValueError(
            f"Invalid {resource_type} ID format: '{resource_id}'. "
            "Expected a valid UUID (e.g., 550e8400-e29b-41d4-a716-446655440000)."
        )
    return resource_id


class SentinelCryptException(Exception):
    """Base exception."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code

    def to_dict(self) -> dict:
        """Return a consistent error response dict."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": {},
            }
        }


# ── Dataset ──────────────────────────────────────────────────────────────────

class InvalidDatasetError(SentinelCryptException):
    def __init__(self, message: str):
        super().__init__(message, "INVALID_DATASET")


class UnsupportedFormatError(SentinelCryptException):
    def __init__(self, message: str):
        super().__init__(message, "UNSUPPORTED_FORMAT")


class DatasetNotFoundError(SentinelCryptException):
    def __init__(self, dataset_id: str):
        super().__init__(f"Dataset '{dataset_id}' not found.", "DATASET_NOT_FOUND")


# ── Models ────────────────────────────────────────────────────────────────────

class ModelNotFoundError(SentinelCryptException):
    def __init__(self, model_id: str):
        super().__init__(f"Model '{model_id}' not found.", "MODEL_NOT_FOUND")


class ModelTrainingError(SentinelCryptException):
    def __init__(self, message: str):
        super().__init__(message, "MODEL_TRAINING_FAILED")


# ── Prediction ────────────────────────────────────────────────────────────────

class InvalidFeaturesError(SentinelCryptException):
    def __init__(self, message: str):
        super().__init__(message, "INVALID_FEATURES")


class PredictionFailedError(SentinelCryptException):
    def __init__(self, message: str):
        super().__init__(message, "PREDICTION_FAILED")


class PredictionNotFoundError(SentinelCryptException):
    def __init__(self, prediction_id: str):
        super().__init__(f"Prediction '{prediction_id}' not found.", "PREDICTION_NOT_FOUND")


# ── Explainability ────────────────────────────────────────────────────────────

class ExplanationFailedError(SentinelCryptException):
    def __init__(self, message: str):
        super().__init__(message, "EXPLANATION_FAILED")


# ── Cryptography ──────────────────────────────────────────────────────────────

class IntegrityVerificationError(SentinelCryptException):
    def __init__(self, message: str, sequence_number: int = -1):
        super().__init__(message, "LEDGER_VERIFICATION_FAILED")
        self.sequence_number = sequence_number


class CryptographicLedgerError(SentinelCryptException):
    def __init__(self, message: str):
        super().__init__(message, "LEDGER_ERROR")


# ── System & Infrastructure Failures ──────────────────────────────────────────

class DatabaseUnavailableError(SentinelCryptException):
    def __init__(self, message: str = "Database connection unavailable or operational failure."):
        super().__init__(message, "DATABASE_UNAVAILABLE")


class DependencyUnavailableError(SentinelCryptException):
    def __init__(self, dependency: str, message: str | None = None):
        msg = message or f"Required dependency '{dependency}' is unavailable."
        super().__init__(msg, "DEPENDENCY_UNAVAILABLE")
        self.dependency = dependency


class ConfigurationError(SentinelCryptException):
    def __init__(self, message: str):
        super().__init__(message, "CONFIGURATION_ERROR")

