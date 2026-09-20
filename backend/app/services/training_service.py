"""Training Service for SentinelCrypt AI.

Coordinates the end-to-end model training lifecycle:
1. Dataset retrieval & verification.
2. Leakage-safe preprocessing & deterministic train/test splitting.
3. Model instantiation & training (Logistic Regression / Random Forest).
4. Comprehensive multi-metric evaluation & latency measurement.
5. Model & preprocessor artifact serialization.
6. Database registration of ModelRecord and optional ModelEvaluation.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.exceptions import (
    DatasetNotFoundError,
    ModelNotFoundError,
    ModelTrainingError,
)
from backend.app.core.logging import get_logger
from backend.app.db.models import ModelRecord
from backend.app.db.repositories.dataset_repository import DatasetRepository
from backend.app.db.repositories.model_evaluation_repository import ModelEvaluationRepository
from backend.app.db.repositories.model_repository import ModelRepository
from backend.app.ml.evaluation.evaluator import ModelEvaluator
from backend.app.ml.preprocessing.pipeline import fit_transform_dataset
from backend.app.ml.registry import ModelRegistry
from backend.app.schemas.model import (
    ModelMetricsResponse,
    ModelResponse,
    ModelTrainRequest,
)
from backend.app.schemas.model_evaluation import ModelEvaluationCreate

logger = get_logger(__name__)


class TrainingService:
    """Orchestrates model training, evaluation, and persistence."""

    def __init__(self, db: Session):
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.model_repo = ModelRepository(db)
        self.eval_repo = ModelEvaluationRepository(db)

    def train_model(self, req: ModelTrainRequest) -> ModelResponse:
        """Execute full training pipeline from dataset to persisted model."""
        logger.info(
            "Initiating model training: dataset_id=%s, model_type=%s, seed=%d",
            req.dataset_id,
            req.model_type,
            req.random_seed,
        )

        # 1. Fetch dataset
        dataset = self.dataset_repo.get_by_id(req.dataset_id)
        if not dataset:
            raise DatasetNotFoundError(req.dataset_id)

        # 2. Locate raw CSV file
        csv_path = Path(settings.DATA_RAW_DIR) / dataset.file_name
        if not csv_path.exists():
            raise ModelTrainingError(
                f"Raw dataset file '{dataset.file_name}' not found on disk at {csv_path}"
            )

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            raise ModelTrainingError(f"Failed to read dataset CSV: {str(e)}") from e

        # 3. Unique identifier for this model run
        model_id = str(uuid.uuid4())
        artifact_prefix = f"{req.model_type}_{model_id[:8]}"

        # 4. Leakage-safe preprocessing
        target_col = dataset.target_column or "label"
        try:
            prep_res = fit_transform_dataset(
                df=df,
                target_column=target_col,
                train_ratio=req.train_ratio,
                random_seed=req.random_seed,
                artifact_name=artifact_prefix,
                save_dir=settings.MODELS_ARTIFACTS_DIR,
            )
        except Exception as e:
            raise ModelTrainingError(f"Preprocessing pipeline failed: {str(e)}") from e

        # 5. Instantiate model
        detector = ModelRegistry.create_model(
            model_type=req.model_type,
            hyperparameters=req.hyperparameters,
            random_seed=req.random_seed,
        )

        # 6. Fit detector on training split
        detector.fit(
            X=prep_res.X_train,
            y=prep_res.y_train,
            feature_names=prep_res.feature_names,
        )

        # 7. Evaluate detector on test split
        evaluator = ModelEvaluator()
        class_labels = [str(c) for c in prep_res.label_encoder.classes_]
        eval_res = evaluator.evaluate(
            model=detector,
            X_test=prep_res.X_test,
            y_test=prep_res.y_test,
            label_names=class_labels,
        )

        # 8. Save model artifact
        version = "v1.0.0"
        model_artifact_path = ModelRegistry.save_model(
            model=detector,
            model_id=model_id,
            version=version,
            save_dir=settings.MODELS_TRAINED_DIR,
        )

        # 9. Persist ModelRecord in database
        clean_name = f"{req.model_type.replace('_', ' ').title()} ({dataset.name})"
        eval_dict = eval_res.to_dict()

        db_model = self.model_repo.create(
            name=clean_name,
            version=version,
            artifact_path=str(model_artifact_path),
            preprocessing_path=str(prep_res.pipeline_path),
            metrics_json=json.dumps(eval_dict),
            feature_schema_json=json.dumps(prep_res.feature_schema),
            experiment_id=req.experiment_id,
            model_id=model_id,
        )

        # 10. Record ModelEvaluation if experiment_id is provided
        if req.experiment_id:
            try:
                self.eval_repo.create(
                    ModelEvaluationCreate(
                        experiment_id=req.experiment_id,
                        model_id=model_id,
                        dataset_id=req.dataset_id,
                        metrics=eval_res.metrics,
                        confusion_matrix=eval_res.confusion_matrix,
                        execution_time_s=eval_res.execution_time_s,
                    )
                )
            except Exception as e:
                logger.warning("Failed to record ModelEvaluation: %s", e)

        logger.info(
            "Model training complete: model_id=%s, accuracy=%.4f, f1_macro=%.4f",
            model_id,
            eval_res.metrics.get("accuracy", 0.0),
            eval_res.metrics.get("f1_macro", 0.0),
        )

        return self._to_model_response(db_model)

    def get_model(self, model_id: str) -> ModelResponse:
        """Fetch model by ID."""
        model = self.model_repo.get_by_id(model_id)
        if not model:
            raise ModelNotFoundError(model_id)
        return self._to_model_response(model)

    def list_models(self, skip: int = 0, limit: int = 100) -> List[ModelResponse]:
        """List all models."""
        models = self.model_repo.get_all(skip=skip, limit=limit)
        return [self._to_model_response(m) for m in models]

    def count_models(self) -> int:
        """Total model count."""
        return self.model_repo.count()

    def get_model_metrics(self, model_id: str) -> ModelMetricsResponse:
        """Return detailed evaluation metrics for a model."""
        model = self.model_repo.get_by_id(model_id)
        if not model:
            raise ModelNotFoundError(model_id)

        eval_data = json.loads(model.metrics_json or "{}")
        metrics = eval_data.get("metrics", {})
        confusion_matrix = eval_data.get("confusion_matrix")
        classification_report = eval_data.get("classification_report")

        return ModelMetricsResponse(
            model_id=model.id,
            model_name=model.name,
            version=model.version,
            metrics=metrics,
            confusion_matrix=confusion_matrix,
            classification_report=classification_report,
        )

    def delete_model(self, model_id: str) -> bool:
        """Delete model record and associated files."""
        model = self.model_repo.get_by_id(model_id)
        if not model:
            raise ModelNotFoundError(model_id)

        # Remove artifacts if they exist
        for p in [model.artifact_path, model.preprocessing_path]:
            if p:
                try:
                    f = Path(p)
                    if f.exists():
                        f.unlink()
                except Exception as e:
                    logger.warning("Could not delete artifact file %s: %s", p, e)

        return self.model_repo.delete(model_id)

    @staticmethod
    def _to_model_response(model: ModelRecord) -> ModelResponse:
        eval_data = json.loads(model.metrics_json or "{}")
        metrics = eval_data.get("metrics", eval_data)
        feature_schema = json.loads(model.feature_schema_json or "[]")

        return ModelResponse(
            id=model.id,
            experiment_id=model.experiment_id,
            name=model.name,
            version=model.version,
            artifact_path=model.artifact_path,
            preprocessing_path=model.preprocessing_path,
            metrics=metrics,
            feature_schema=feature_schema,
            created_at=model.created_at,
        )
