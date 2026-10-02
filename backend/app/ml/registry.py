"""Model Registry for SentinelCrypt AI.

Manages model types, instantiation, artifact persistence, and loading with
deterministic versioning.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union
import joblib

from backend.app.core.config import settings
from backend.app.core.exceptions import ModelNotFoundError, ModelTrainingError
from backend.app.core.logging import get_logger
from backend.app.ml.models.base import BaseDetector
from backend.app.ml.models.logistic_regression import LogisticRegressionDetector
from backend.app.ml.models.random_forest import RandomForestDetector

logger = get_logger(__name__)


class ModelRegistry:
    """Registry and artifact manager for intrusion detection models."""

    _MODELS: Dict[str, Type[BaseDetector]] = {
        "logistic_regression": LogisticRegressionDetector,
        "random_forest": RandomForestDetector,
    }

    @classmethod
    def get_supported_model_types(cls) -> list[str]:
        """Return core model types plus registered model plugins."""
        types = list(cls._MODELS.keys())
        try:
            from backend.app.plugins.registry import get_registry

            for item in get_registry().list("model"):
                if item["name"] not in types:
                    types.append(item["name"])
        except Exception:
            pass
        return types

    @classmethod
    def get_model_class(cls, model_type: str) -> Type[BaseDetector]:
        """Lookup model class by type string."""
        model_type_clean = model_type.strip().lower()
        if model_type_clean in cls._MODELS:
            return cls._MODELS[model_type_clean]

        from backend.app.plugins.registry import get_registry

        info = get_registry().get("model", model_type_clean)
        factory = None if info is None else info.factory
        if isinstance(factory, type) and issubclass(factory, BaseDetector):
            return factory

        supported = ", ".join(cls.get_supported_model_types())
        raise ModelTrainingError(
            f"Unsupported model type '{model_type}'. Supported: {supported}"
        )

    @classmethod
    def create_model(
        cls,
        model_type: str,
        hyperparameters: Optional[Dict[str, Any]] = None,
        random_seed: int = 42,
    ) -> BaseDetector:
        """Instantiate a new detector instance."""
        model_cls = cls.get_model_class(model_type)
        return model_cls(hyperparameters=hyperparameters, random_seed=random_seed)

    @classmethod
    def save_model(
        cls,
        model: BaseDetector,
        model_id: str,
        version: str = "v1.0.0",
        save_dir: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Save a fitted detector to models/trained/."""
        directory = Path(save_dir or settings.MODELS_TRAINED_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{model.model_type}_{model_id}_{version}.joblib"
        artifact_path = directory / filename
        model.save(artifact_path)
        logger.info("Saved model artifact to %s", artifact_path)
        return artifact_path

    @classmethod
    def load_model(cls, artifact_path: Union[str, Path]) -> BaseDetector:
        """Load a persisted model detector by path."""
        path = Path(artifact_path)
        if not path.exists():
            raise ModelNotFoundError(f"Model artifact at {path} does not exist.")

        # Read metadata payload
        payload = joblib.load(path)
        model_type = payload.get("model_type")
        if not model_type:
            raise ModelNotFoundError(f"Corrupt model artifact at {path}: missing model_type.")

        model_cls = cls.get_model_class(model_type)
        return model_cls.load(path)

    @classmethod
    def load_preprocessing_pipeline(cls, preprocessing_path: Union[str, Path]) -> Dict[str, Any]:
        """Load fitted preprocessing pipeline artifact dictionary."""
        path = Path(preprocessing_path)
        if not path.exists():
            raise FileNotFoundError(f"Preprocessing artifact at {path} does not exist.")
        with open(path, "rb") as f:
            return pickle.load(f)
