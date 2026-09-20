"""Structured application exceptions for SentinelCrypt AI."""


class SentinelCryptException(Exception):
    """Base exception."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


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
