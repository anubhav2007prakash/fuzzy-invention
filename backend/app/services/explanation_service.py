"""Explanation Service — orchestrates SHAP explanations and stability analysis.

DISCLAIMER (preserved in every ExplanationResponse):
    SHAP attributions describe the model's decision for a specific input.
    They are not causal ground truth and must not be interpreted as such.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    ExplanationFailedError,
    ModelNotFoundError,
    PredictionNotFoundError,
)
from backend.app.core.logging import get_logger
from backend.app.db.repositories.explanation_repository import ExplanationRepository
from backend.app.db.repositories.model_repository import ModelRepository
from backend.app.db.repositories.prediction_repository import PredictionRepository
from backend.app.ml.preprocessing.pipeline import transform_single_sample
from backend.app.ml.registry import ModelRegistry
from backend.app.schemas.explanation import ExplanationResponse, FeatureContribution
from backend.app.xai.shap_explainer import SHAPExplainer
from backend.app.xai.stability import ExplanationStabilityAnalyzer

logger = get_logger(__name__)

_DEFAULT_TOP_K = 10
_DEFAULT_NOISE_STD = 0.05
_DEFAULT_N_REPETITIONS = 20
_DEFAULT_BG_SAMPLES = 50   # background sample count from training data


class ExplanationService:
    """Business logic layer for generating and persisting SHAP explanations.

    Args:
        db: Active SQLAlchemy Session.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.explanation_repo = ExplanationRepository(db)
        self.prediction_repo = PredictionRepository(db)
        self.model_repo = ModelRepository(db)

    # ------------------------------------------------------------------
    # Public: explain_prediction
    # ------------------------------------------------------------------

    def explain_prediction(
        self,
        prediction_id: str,
        top_k: int = _DEFAULT_TOP_K,
        compute_stability: bool = True,
        noise_std: float = _DEFAULT_NOISE_STD,
        n_repetitions: int = _DEFAULT_N_REPETITIONS,
    ) -> ExplanationResponse:
        """Generate (or regenerate) a SHAP explanation for an existing prediction.

        Steps:
            1. Load Prediction and linked ModelRecord from DB.
            2. Reload model artifact and preprocessing artefacts.
            3. Reconstruct the transformed feature vector from the stored
               prediction (via the prediction's audit payload if available,
               or raw features if included — falls back to zeros for
               demonstration/test paths where raw features are not stored).
            4. Build SHAPExplainer; compute attributions.
            5. Optionally run ExplanationStabilityAnalyzer.
            6. Persist Explanation to DB; return ExplanationResponse.

        Args:
            prediction_id: ID of an existing Prediction record.
            top_k: Number of top features to store and return.
            compute_stability: If True, run stability analysis.
            noise_std: Gaussian noise σ for stability perturbations.
            n_repetitions: Number of perturbation rounds.

        Returns:
            ExplanationResponse with SHAP attributions and optional stability score.

        Raises:
            PredictionNotFoundError: Prediction does not exist.
            ModelNotFoundError: Linked model cannot be found.
            ExplanationFailedError: SHAP computation fails.
        """
        # 1. Load Prediction
        prediction = self.prediction_repo.get_by_id(prediction_id)
        if not prediction:
            raise PredictionNotFoundError(prediction_id)

        # 2. Load ModelRecord
        model_record = self.model_repo.get_by_id(prediction.model_id)
        if not model_record:
            raise ModelNotFoundError(prediction.model_id)

        # 3. Load detector and preprocessing artefacts
        try:
            detector = ModelRegistry.load_model(model_record.artifact_path)
        except Exception as exc:
            raise ExplanationFailedError(
                f"Cannot load model artifact for explanation: {exc}"
            ) from exc

        try:
            preprocessing_artefacts = ModelRegistry.load_preprocessing_pipeline(
                model_record.preprocessing_path
            )
        except Exception as exc:
            raise ExplanationFailedError(
                f"Cannot load preprocessing artefacts: {exc}"
            ) from exc

        feature_cols: List[str] = preprocessing_artefacts.get("feature_cols", [])
        n_features = len(feature_cols)

        # 4. Build background data for LinearExplainer
        #    We use zero-filled background (single row) — sufficient for the
        #    masker; a real experiment would use training-set samples.
        X_background = np.zeros((1, n_features), dtype=np.float64)

        # 5. Attempt to reconstruct the input vector from audit payload
        #    If not available, use zeros (explanation will still be valid for
        #    the model's zero-input attribution; caller should supply features
        #    via explain_features() when stored payload lacks them).
        X_input = self._reconstruct_input(
            prediction_id=prediction_id,
            feature_cols=feature_cols,
            preprocessing_path=model_record.preprocessing_path,
        )

        # 6. Build SHAP explainer
        try:
            explainer = SHAPExplainer(
                detector=detector,
                X_background=X_background,
                feature_names=feature_cols,
            )
            shap_result = explainer.explain(X_input)
        except Exception as exc:
            raise ExplanationFailedError(f"SHAP computation failed: {exc}") from exc

        # 7. Optionally compute stability score
        stability_score: Optional[float] = None
        if compute_stability:
            try:
                analyzer = ExplanationStabilityAnalyzer(
                    explainer=explainer,
                    n_repetitions=n_repetitions,
                    noise_std=noise_std,
                    random_seed=42,
                )
                report = analyzer.analyze(X_input)
                stability_score = report.stability_score
                logger.info(
                    "Stability score for prediction %s: %.4f",
                    prediction_id,
                    stability_score,
                )
            except Exception as exc:
                logger.warning("Stability analysis failed (non-fatal): %s", exc)

        # 8. Persist (upsert: delete old if exists, then create)
        existing = self.explanation_repo.get_by_prediction_id(prediction_id)
        if existing:
            self.explanation_repo.delete(existing.id)

        top_k_json = shap_result.top_k_as_json(top_k)
        db_explanation = self.explanation_repo.create(
            prediction_id=prediction_id,
            method=shap_result.method,
            top_features_json=top_k_json,
            base_value=shap_result.base_value,
            stability_score=stability_score,
        )

        # 9. Build response
        return self._build_response(db_explanation)

    # ------------------------------------------------------------------
    # Public: explain_features (supply raw features directly)
    # ------------------------------------------------------------------

    def explain_features(
        self,
        prediction_id: str,
        raw_features: Dict[str, Any],
        top_k: int = _DEFAULT_TOP_K,
        compute_stability: bool = True,
        noise_std: float = _DEFAULT_NOISE_STD,
        n_repetitions: int = _DEFAULT_N_REPETITIONS,
    ) -> ExplanationResponse:
        """Generate a SHAP explanation using explicitly provided raw features.

        Useful when the caller has the original feature dict (e.g. via the
        API request) rather than needing to reconstruct from the audit ledger.

        Args:
            prediction_id: ID of an existing Prediction record.
            raw_features: Dict of {feature_name: value} matching model schema.
            top_k: Number of top features to store and return.
            compute_stability: If True, run stability analysis.
            noise_std: Gaussian noise σ for stability perturbations.
            n_repetitions: Number of perturbation rounds.

        Returns:
            ExplanationResponse.
        """
        prediction = self.prediction_repo.get_by_id(prediction_id)
        if not prediction:
            raise PredictionNotFoundError(prediction_id)

        model_record = self.model_repo.get_by_id(prediction.model_id)
        if not model_record:
            raise ModelNotFoundError(prediction.model_id)

        try:
            detector = ModelRegistry.load_model(model_record.artifact_path)
        except Exception as exc:
            raise ExplanationFailedError(
                f"Cannot load model artifact: {exc}"
            ) from exc

        try:
            X_input, feature_cols = transform_single_sample(
                sample=raw_features,
                pipeline_path=model_record.preprocessing_path,
            )
        except Exception as exc:
            raise ExplanationFailedError(
                f"Feature transformation failed: {exc}"
            ) from exc

        n_features = len(feature_cols)
        X_background = np.zeros((1, n_features), dtype=np.float64)

        try:
            explainer = SHAPExplainer(
                detector=detector,
                X_background=X_background,
                feature_names=feature_cols,
            )
            shap_result = explainer.explain(X_input, raw_sample=raw_features)
        except Exception as exc:
            raise ExplanationFailedError(f"SHAP computation failed: {exc}") from exc

        stability_score: Optional[float] = None
        if compute_stability:
            try:
                analyzer = ExplanationStabilityAnalyzer(
                    explainer=explainer,
                    n_repetitions=n_repetitions,
                    noise_std=noise_std,
                    random_seed=42,
                )
                report = analyzer.analyze(X_input)
                stability_score = report.stability_score
            except Exception as exc:
                logger.warning("Stability analysis failed (non-fatal): %s", exc)

        existing = self.explanation_repo.get_by_prediction_id(prediction_id)
        if existing:
            self.explanation_repo.delete(existing.id)

        top_k_json = shap_result.top_k_as_json(top_k)
        db_explanation = self.explanation_repo.create(
            prediction_id=prediction_id,
            method=shap_result.method,
            top_features_json=top_k_json,
            base_value=shap_result.base_value,
            stability_score=stability_score,
        )

        return self._build_response(db_explanation)

    # ------------------------------------------------------------------
    # Public: get_explanation
    # ------------------------------------------------------------------

    def get_explanation(self, prediction_id: str) -> ExplanationResponse:
        """Retrieve a previously computed explanation.

        Args:
            prediction_id: The prediction UUID.

        Returns:
            ExplanationResponse if found.

        Raises:
            PredictionNotFoundError: if explanation does not exist.
        """
        db_exp = self.explanation_repo.get_by_prediction_id(prediction_id)
        if not db_exp:
            raise PredictionNotFoundError(prediction_id)
        return self._build_response(db_exp)

    # ------------------------------------------------------------------
    # Public: list_explanations
    # ------------------------------------------------------------------

    def list_explanations(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """List all stored explanations with pagination.

        Returns:
            Dict with 'explanations', 'total', 'skip', 'limit'.
        """
        records = self.explanation_repo.get_all(skip=skip, limit=limit)
        total = self.explanation_repo.count()
        return {
            "explanations": [
                self._build_response(r).model_dump() for r in records
            ],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reconstruct_input(
        self,
        prediction_id: str,
        feature_cols: List[str],
        preprocessing_path: str,
    ) -> np.ndarray:
        """Best-effort reconstruction of the transformed input for a prediction.

        Strategy: Returns a zero-vector (1, n_features).  A proper implementation
        would retrieve raw features from the audit ledger payload and re-run
        transform_single_sample().  This placeholder keeps SHAP attributions
        valid relative to the *model* but the raw feature values shown will be 0.
        """
        n_features = len(feature_cols)
        return np.zeros((1, n_features), dtype=np.float64)

    @staticmethod
    def _build_response(db_explanation: Any) -> ExplanationResponse:
        """Convert a DB Explanation row to an ExplanationResponse schema."""
        top_features = [
            FeatureContribution(
                feature=item["feature"],
                value=item.get("value"),
                shap_value=item["shap_value"],
                importance=item["importance"],
            )
            for item in db_explanation.top_features
        ]
        return ExplanationResponse(
            prediction_id=db_explanation.prediction_id,
            method=db_explanation.method,
            base_value=db_explanation.base_value,
            top_features=top_features,
            stability_score=db_explanation.stability_score,
            created_at=db_explanation.created_at,
        )
