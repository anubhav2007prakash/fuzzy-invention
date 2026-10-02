"""Prediction Service — Inference orchestrator and cryptographic evidence packaging."""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    ModelNotFoundError,
    PredictionFailedError,
    PredictionNotFoundError,
)
from backend.app.core.logging import get_logger
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hashing import sha256_hash
from backend.app.db.models import ArtifactLineage, Prediction
from backend.app.db.repositories.model_repository import ModelRepository
from backend.app.db.repositories.prediction_repository import PredictionRepository
from backend.app.ml.preprocessing.pipeline import (
    transform_batch_samples,
    transform_single_sample,
)
from backend.app.ml.registry import ModelRegistry
from backend.app.schemas.prediction import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    PredictionRequest,
    PredictionResponse,
)
from backend.app.services.audit_service import AuditService

logger = get_logger(__name__)


class PredictionService:
    def __init__(self, db: Session):
        self.db = db
        self.model_repo = ModelRepository(db)
        self.prediction_repo = PredictionRepository(db)
        self.audit_service = AuditService(db)

    def predict(
        self,
        req: PredictionRequest,
        request_source: str = "api",
    ) -> PredictionResponse:
        """Execute single sample inference, package evidence, and anchor into cryptographic ledger."""
        model_record = self.model_repo.get_by_id(req.model_id)
        if not model_record:
            raise ModelNotFoundError(req.model_id)

        # 1. Compute canonical input hash of raw features
        input_hash = sha256_hash(canonicalize(req.features))

        # 2. Load model detector
        try:
            detector = ModelRegistry.load_model(model_record.artifact_path)
        except Exception as e:
            raise PredictionFailedError(f"Failed to load model artifact: {str(e)}") from e

        # 3. Transform single sample using saved preprocessing pipeline
        try:
            X_transformed, feature_cols = transform_single_sample(
                sample=req.features,
                pipeline_path=model_record.preprocessing_path,
            )
        except Exception as e:
            raise PredictionFailedError(f"Feature transformation failed: {str(e)}") from e

        # 4. Measure inference execution latency
        start_time = time.perf_counter()
        try:
            pred_arr = detector.predict(X_transformed)
            pred_label = int(pred_arr[0])
            latency_ms = (time.perf_counter() - start_time) * 1000.0
        except Exception as e:
            raise PredictionFailedError(f"Inference execution failed: {str(e)}") from e

        # 5. Extract probabilities if supported
        probabilities: Optional[Dict[str, float]] = None
        try:
            prob_arr = detector.predict_proba(X_transformed)[0]
            if detector.classes_ is not None:
                probabilities = {
                    str(c): float(round(p, 6))
                    for c, p in zip(detector.classes_, prob_arr)
                }
        except Exception as e:
            logger.debug("Probabilities not available: %s", e)

        # Class name resolution
        if detector.classes_ is not None and pred_label < len(detector.classes_):
            predicted_class = str(detector.classes_[pred_label])
        else:
            predicted_class = str(pred_label)

        # 5b. Confidence thresholding
        confidence: Optional[float] = None
        is_uncertain = False
        if probabilities and req.confidence_threshold is not None:
            max_prob = max(probabilities.values())
            confidence = float(round(max_prob, 6))
            if max_prob < req.confidence_threshold:
                predicted_class = "UNCERTAIN"
                is_uncertain = True

        # 6. Generate UUID & timestamp for prediction and evidence
        prediction_id = str(uuid.uuid4())
        created_at_dt = datetime.now(timezone.utc)
        created_at_iso = created_at_dt.isoformat()

        # 7. Package canonical evidence payload
        evidence_payload = {
            "event_type": "INFERENCE",
            "features": req.features,
            "input_hash": input_hash,
            "latency_ms": round(latency_ms, 4),
            "model_id": model_record.id,
            "model_version": model_record.version,
            "predicted_class": predicted_class,
            "prediction_id": prediction_id,
            "prediction_label": pred_label,
            "probabilities": probabilities,
            "timestamp": created_at_iso,
        }

        # 8. Persist Prediction record
        probs_json = json.dumps(probabilities) if probabilities else None
        db_prediction = self.prediction_repo.create(
            prediction_id=prediction_id,
            model_id=model_record.id,
            input_hash=input_hash,
            predicted_class=predicted_class,
            probabilities_json=probs_json,
            latency_ms=round(latency_ms, 4),
            request_source=request_source,
        )

        # 9. Anchor evidence into cryptographic audit chain
        audit_record = self.audit_service.create_audit_entry(
            prediction_id=prediction_id,
            evidence_payload=evidence_payload,
        )
        from backend.app.services.lineage_service import ArtifactLineageService, artifact_digest

        model_parent = f"model:{model_record.id}"
        model_lineage_exists = self.db.get(ArtifactLineage, model_parent) is not None
        ArtifactLineageService(self.db).record_chain([{
            "artifact_id": f"prediction:{prediction_id}",
            "artifact_type": "prediction",
            "parent_artifact_id": model_parent if model_lineage_exists else None,
            "created_at": db_prediction.created_at,
            "version": "1",
            "sha256": artifact_digest(evidence_payload),
            "experiment_id": model_record.experiment_id,
            "metadata": {
                "model_id": model_record.id,
                "input_hash": input_hash,
                "predicted_class": predicted_class,
                "digest_scope": "canonical prediction evidence payload",
                **({} if model_lineage_exists else {
                    "lineage_warning": "Registered model has no lineage record.",
                }),
            },
        }])
        ArtifactLineageService(self.db).record_chain([{
            "artifact_id": f"evidence:{audit_record.id}",
            "artifact_type": "cryptographic_evidence",
            "parent_artifact_id": f"prediction:{prediction_id}",
            "created_at": audit_record.created_at,
            "version": "1",
            "sha256": audit_record.record_hash,
            "experiment_id": model_record.experiment_id,
            "metadata": {
                "prediction_id": prediction_id,
                "sequence_number": audit_record.sequence_number,
                "previous_hash": audit_record.previous_hash,
                "digest_scope": "existing audit-chain record hash",
            },
        }])

        return PredictionResponse(
            prediction_id=db_prediction.id,
            model_id=db_prediction.model_id,
            model_version=model_record.version,
            predicted_class=db_prediction.predicted_class,
            prediction_label=pred_label,
            probabilities=probabilities,
            confidence=confidence,
            is_uncertain=is_uncertain,
            input_hash=db_prediction.input_hash,
            latency_ms=db_prediction.latency_ms,
            created_at=db_prediction.created_at,
        )

    def predict_batch(
        self,
        req: BatchPredictionRequest,
        request_source: str = "api_batch",
    ) -> BatchPredictionResponse:
        """Execute vectorized batch inference and sequentially anchor each record into the ledger."""
        if not req.samples:
            return BatchPredictionResponse(
                total_samples=0,
                predictions=[],
                processing_time_ms=0.0,
            )

        model_record = self.model_repo.get_by_id(req.model_id)
        if not model_record:
            raise ModelNotFoundError(req.model_id)

        detector = ModelRegistry.load_model(model_record.artifact_path)

        # Batch transform
        t_batch_start = time.perf_counter()
        X_batch, _ = transform_batch_samples(req.samples, model_record.preprocessing_path)

        # Batch predict
        y_preds = detector.predict(X_batch)
        try:
            y_probs = detector.predict_proba(X_batch)
        except Exception:
            y_probs = None

        batch_latency_total = (time.perf_counter() - t_batch_start) * 1000.0
        sample_latency = batch_latency_total / len(req.samples)

        responses: List[PredictionResponse] = []

        for i, sample in enumerate(req.samples):
            pred_label = int(y_preds[i])
            if detector.classes_ is not None and pred_label < len(detector.classes_):
                predicted_class = str(detector.classes_[pred_label])
            else:
                predicted_class = str(pred_label)

            probs_dict = None
            if y_probs is not None:
                probs_dict = {
                    str(c): float(round(p, 6))
                    for c, p in zip(detector.classes_, y_probs[i])
                }

            input_hash = sha256_hash(canonicalize(sample))
            prediction_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()

            evidence_payload = {
                "event_type": "INFERENCE",
                "features": sample,
                "input_hash": input_hash,
                "latency_ms": round(sample_latency, 4),
                "model_id": model_record.id,
                "model_version": model_record.version,
                "predicted_class": predicted_class,
                "prediction_id": prediction_id,
                "prediction_label": pred_label,
                "probabilities": probs_dict,
                "timestamp": now_iso,
            }

            probs_json = json.dumps(probs_dict) if probs_dict else None
            db_prediction = self.prediction_repo.create(
                prediction_id=prediction_id,
                model_id=model_record.id,
                input_hash=input_hash,
                predicted_class=predicted_class,
                probabilities_json=probs_json,
                latency_ms=round(sample_latency, 4),
                request_source=request_source,
            )

            audit_record = self.audit_service.create_audit_entry(
                prediction_id=prediction_id,
                evidence_payload=evidence_payload,
            )
            from backend.app.services.lineage_service import ArtifactLineageService, artifact_digest

            model_parent = f"model:{model_record.id}"
            model_lineage_exists = self.db.get(ArtifactLineage, model_parent) is not None
            ArtifactLineageService(self.db).record_chain([{
                "artifact_id": f"prediction:{prediction_id}",
                "artifact_type": "prediction",
                "parent_artifact_id": model_parent if model_lineage_exists else None,
                "created_at": db_prediction.created_at,
                "version": "1",
                "sha256": artifact_digest(evidence_payload),
                "experiment_id": model_record.experiment_id,
                "metadata": {
                    "model_id": model_record.id,
                    "input_hash": input_hash,
                    "predicted_class": predicted_class,
                    "digest_scope": "canonical prediction evidence payload",
                    **({} if model_lineage_exists else {
                        "lineage_warning": "Registered model has no lineage record.",
                    }),
                },
            }])
            ArtifactLineageService(self.db).record_chain([{
                "artifact_id": f"evidence:{audit_record.id}",
                "artifact_type": "cryptographic_evidence",
                "parent_artifact_id": f"prediction:{prediction_id}",
                "created_at": audit_record.created_at,
                "version": "1",
                "sha256": audit_record.record_hash,
                "experiment_id": model_record.experiment_id,
                "metadata": {
                    "prediction_id": prediction_id,
                    "sequence_number": audit_record.sequence_number,
                    "previous_hash": audit_record.previous_hash,
                    "digest_scope": "existing audit-chain record hash",
                },
            }])

            responses.append(
                PredictionResponse(
                    prediction_id=db_prediction.id,
                    model_id=db_prediction.model_id,
                    model_version=model_record.version,
                    predicted_class=db_prediction.predicted_class,
                    prediction_label=pred_label,
                    probabilities=probs_dict,
                    input_hash=db_prediction.input_hash,
                    latency_ms=db_prediction.latency_ms,
                    created_at=db_prediction.created_at,
                )
            )

        total_elapsed_ms = (time.perf_counter() - t_batch_start) * 1000.0
        return BatchPredictionResponse(
            total_samples=len(responses),
            predictions=responses,
            processing_time_ms=round(total_elapsed_ms, 2),
        )

    def get_prediction(self, prediction_id: str) -> PredictionResponse:
        """Fetch a specific prediction by UUID."""
        pred = self.prediction_repo.get_by_id(prediction_id)
        if not pred:
            raise PredictionNotFoundError(prediction_id)

        model = self.model_repo.get_by_id(pred.model_id)
        version = model.version if model else "v1.0.0"

        probs = json.loads(pred.probabilities_json) if pred.probabilities_json else None
        # Infer prediction label int if possible
        try:
            pred_label = int(pred.predicted_class)
        except ValueError:
            pred_label = 1 if pred.predicted_class.upper() in ["ATTACK", "MALICIOUS", "1"] else 0

        return PredictionResponse(
            prediction_id=pred.id,
            model_id=pred.model_id,
            model_version=version,
            predicted_class=pred.predicted_class,
            prediction_label=pred_label,
            probabilities=probs,
            input_hash=pred.input_hash,
            latency_ms=pred.latency_ms,
            created_at=pred.created_at,
        )

    def list_predictions(
        self,
        skip: int = 0,
        limit: int = 100,
        model_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List predictions with pagination."""
        records = self.prediction_repo.get_all(skip=skip, limit=limit, model_id=model_id)
        total = self.prediction_repo.count(model_id=model_id)

        items = []
        for r in records:
            model = self.model_repo.get_by_id(r.model_id)
            version = model.version if model else "v1.0.0"
            probs = json.loads(r.probabilities_json) if r.probabilities_json else None
            try:
                pred_label = int(r.predicted_class)
            except ValueError:
                pred_label = 1 if r.predicted_class.upper() in ["ATTACK", "MALICIOUS", "1"] else 0

            items.append(
                PredictionResponse(
                    prediction_id=r.id,
                    model_id=r.model_id,
                    model_version=version,
                    predicted_class=r.predicted_class,
                    prediction_label=pred_label,
                    probabilities=probs,
                    input_hash=r.input_hash,
                    latency_ms=r.latency_ms,
                    created_at=r.created_at,
                ).model_dump()
            )

        return {
            "predictions": items,
            "total": total,
            "skip": skip,
            "limit": limit,
        }
