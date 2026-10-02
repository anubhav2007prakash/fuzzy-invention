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
import os
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
from backend.app.cryptography.hashing import hash_file, sha256_hash
from backend.app.db.models import ModelRecord
from backend.app.db.repositories.dataset_repository import DatasetRepository
from backend.app.db.repositories.model_evaluation_repository import ModelEvaluationRepository
from backend.app.db.repositories.model_repository import ModelRepository
from backend.app.ml.evaluation.evaluator import ModelEvaluator
from backend.app.ml.calibration import (
    calibration_report,
    fit_probability_calibrator,
)
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

        raw_dataset_hash = hash_file(str(csv_path))
        if raw_dataset_hash != dataset.file_hash:
            raise ModelTrainingError(
                f"Raw dataset integrity check failed for dataset '{dataset.id}': "
                "the stored file does not match its registered SHA-256."
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
                calibration_fraction=(
                    req.calibration_fraction if req.calibration_method else 0.0
                ),
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

        # 7. Fit optional calibration only on its reserved training partition.
        calibration_metadata: Dict[str, Any] = {
            "enabled": False,
            "method": "none",
            "evaluation_partition": "held_out_test",
        }
        raw_test_probabilities = None
        if len(prep_res.label_encoder.classes_) == 2:
            raw_test_probabilities = detector.predict_proba(prep_res.X_test)
            calibration_metadata["before"] = calibration_report(
                prep_res.y_test, raw_test_probabilities[:, 1]
            )
            if req.calibration_method:
                if prep_res.X_calibration is None or prep_res.y_calibration is None:
                    raise ModelTrainingError(
                        "Calibration was requested but no calibration partition was reserved."
                    )
                try:
                    calibrator = fit_probability_calibrator(
                        method=req.calibration_method,
                        y_calibration=prep_res.y_calibration,
                        calibration_probabilities=detector.predict_proba(
                            prep_res.X_calibration
                        ),
                        classes=detector.classes_,
                    )
                    detector.set_calibrator(calibrator)
                    calibrated_probabilities = detector.predict_proba(prep_res.X_test)
                    calibration_metadata = {
                        "enabled": True,
                        **calibrator.configuration,
                        "calibration_fraction_of_training_partition": req.calibration_fraction,
                        "evaluation_partition": "held_out_test",
                        "evaluation_sample_count": int(len(prep_res.y_test)),
                        "comparison_uses_same_test_observations": True,
                        "before": calibration_metadata["before"],
                        "after": calibration_report(
                            prep_res.y_test, calibrated_probabilities[:, 1]
                        ),
                    }
                except ValueError as e:
                    raise ModelTrainingError(f"Probability calibration failed: {e}") from e
        else:
            calibration_metadata["status"] = "unavailable"
            calibration_metadata["reason"] = (
                "Current post-hoc calibration supports binary targets encoded as 0/1 only."
            )
            if req.calibration_method:
                raise ModelTrainingError(calibration_metadata["reason"])

        # 8. Evaluate detector on the same held-out test partition.
        evaluator = ModelEvaluator()
        class_labels = [str(c) for c in prep_res.label_encoder.classes_]
        eval_res = evaluator.evaluate(
            model=detector,
            X_test=prep_res.X_test,
            y_test=prep_res.y_test,
            label_names=class_labels,
        )

        # 9. Save model artifact including the optional calibration mapping.
        version = "v1.0.0"
        model_artifact_path = ModelRegistry.save_model(
            model=detector,
            model_id=model_id,
            version=version,
            save_dir=settings.MODELS_TRAINED_DIR,
        )

        # 10. Persist evaluation and calibration metadata.
        clean_name = f"{req.model_type.replace('_', ' ').title()} ({dataset.name})"
        eval_dict = eval_res.to_dict()
        eval_dict["calibration"] = calibration_metadata

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

        from backend.app.services.lineage_service import (
            ArtifactLineageService,
            artifact_digest,
        )

        raw_id = f"dataset:{dataset.id}:raw"
        validated_id = f"dataset:{dataset.id}:validated"
        processed_id = f"processed-dataset:{model_id}"
        config_id = f"training-config:{model_id}"
        experiment_artifact_id = f"experiment-run:{model_id}"
        model_artifact_id = f"model:{model_id}"
        results_id = f"results:training:{model_id}"
        report_id = f"report:training:{model_id}"
        label_distribution = json.loads(dataset.label_distribution or "{}")
        processed_payload = {
            "feature_names": prep_res.feature_names,
            "x_train_sha256": sha256_hash(prep_res.X_train.tobytes()),
            "x_test_sha256": sha256_hash(prep_res.X_test.tobytes()),
            "y_train_sha256": sha256_hash(prep_res.y_train.tobytes()),
            "y_test_sha256": sha256_hash(prep_res.y_test.tobytes()),
            "x_train_shape": list(prep_res.X_train.shape),
            "x_test_shape": list(prep_res.X_test.shape),
            "x_train_dtype": str(prep_res.X_train.dtype),
            "x_test_dtype": str(prep_res.X_test.dtype),
            "y_train_dtype": str(prep_res.y_train.dtype),
            "y_test_dtype": str(prep_res.y_test.dtype),
        }
        if prep_res.X_calibration is not None and prep_res.y_calibration is not None:
            processed_payload.update({
                "x_calibration_sha256": sha256_hash(prep_res.X_calibration.tobytes()),
                "y_calibration_sha256": sha256_hash(prep_res.y_calibration.tobytes()),
                "x_calibration_shape": list(prep_res.X_calibration.shape),
                "y_calibration_shape": list(prep_res.y_calibration.shape),
            })
        config_payload = {
            "dataset_id": dataset.id,
            "model_type": req.model_type,
            "hyperparameters": req.hyperparameters,
            "random_seed": req.random_seed,
            "train_ratio": req.train_ratio,
            "calibration_method": req.calibration_method or "none",
            "calibration_fraction_of_training_partition": (
                req.calibration_fraction if req.calibration_method else 0.0
            ),
            "target_column": target_col,
            "feature_schema": prep_res.feature_schema,
            "calibration_metadata": calibration_metadata,
        }
        model_payload = {
            "model_sha256": hash_file(str(model_artifact_path)),
            "preprocessing_sha256": hash_file(str(prep_res.pipeline_path)),
        }
        git_commit = (
            os.environ.get("GIT_COMMIT")
            or os.environ.get("CI_COMMIT_SHA")
            or os.environ.get("GITHUB_SHA")
        )
        lineage_nodes = [
            {
                "artifact_id": raw_id,
                "artifact_type": "raw_dataset",
                "sha256": raw_dataset_hash,
                "version": "1",
                "metadata": {
                    "dataset_id": dataset.id,
                    "file_name": dataset.file_name,
                    "digest_scope": "stored raw file bytes",
                },
            },
            {
                "artifact_id": validated_id,
                "artifact_type": "validated_dataset",
                "parent_artifact_id": raw_id,
                "sha256": artifact_digest({
                    "validation_status": dataset.validation_status,
                    "row_count": dataset.row_count,
                    "feature_count": dataset.feature_count,
                    "target_column": dataset.target_column,
                    "label_distribution": label_distribution,
                }),
                "version": "1",
                "metadata": {
                    "dataset_id": dataset.id,
                    "validation_status": dataset.validation_status,
                    "row_count": dataset.row_count,
                    "feature_count": dataset.feature_count,
                    "target_column": dataset.target_column,
                    "label_distribution": label_distribution,
                    "digest_scope": "canonical validation summary",
                },
            },
            {
                "artifact_id": processed_id,
                "artifact_type": "processed_dataset",
                "parent_artifact_id": validated_id,
                "sha256": artifact_digest(processed_payload),
                "version": "1",
                "metadata": processed_payload,
            },
            {
                "artifact_id": config_id,
                "artifact_type": "training_configuration",
                "parent_artifact_id": processed_id,
                "sha256": artifact_digest(config_payload),
                "version": "1",
                "experiment_id": req.experiment_id,
                "git_commit": git_commit,
                "metadata": config_payload,
            },
            {
                "artifact_id": experiment_artifact_id,
                "artifact_type": "experiment",
                "parent_artifact_id": config_id,
                "sha256": artifact_digest({
                    "configuration": config_payload,
                    "metrics": eval_dict,
                }),
                "version": "1",
                "experiment_id": req.experiment_id,
                "git_commit": git_commit,
                "metadata": {
                    "database_experiment_id": req.experiment_id,
                    "training_run_id": model_id,
                },
            },
            {
                "artifact_id": model_artifact_id,
                "artifact_type": "model",
                "parent_artifact_id": config_id,
                "sha256": artifact_digest(model_payload),
                "version": version,
                "experiment_id": req.experiment_id,
                "git_commit": git_commit,
                "metadata": {
                    "model_id": model_id,
                    "artifact_file": Path(model_artifact_path).name,
                    "preprocessing_file": Path(prep_res.pipeline_path).name,
                    **model_payload,
                },
            },
            {
                "artifact_id": results_id,
                "artifact_type": "results",
                "parent_artifact_id": model_artifact_id,
                "sha256": artifact_digest(eval_dict),
                "version": "1",
                "experiment_id": req.experiment_id,
                "git_commit": git_commit,
                "metadata": {"metrics": eval_dict},
            },
            {
                "artifact_id": report_id,
                "artifact_type": "report",
                "parent_artifact_id": results_id,
                "sha256": artifact_digest({
                    "model_id": model_id,
                    "dataset_id": dataset.id,
                    "metrics": eval_dict,
                }),
                "version": "1",
                "experiment_id": req.experiment_id,
                "git_commit": git_commit,
                "metadata": {
                    "model_id": model_id,
                    "dataset_id": dataset.id,
                    "summary": "Training evaluation report",
                },
            },
        ]
        ArtifactLineageService(self.db).record_chain(lineage_nodes)

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
            calibration=eval_data.get("calibration", {}),
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
            calibration=eval_data.get("calibration", {}),
            feature_schema=feature_schema,
            created_at=model.created_at,
        )
