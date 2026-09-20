"""Explanation Pydantic Schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class FeatureContribution(BaseModel):
    feature: str
    value: Any
    shap_value: float
    importance: float


class ExplanationResponse(BaseModel):
    prediction_id: str
    method: str
    base_value: Optional[float] = None
    top_features: List[FeatureContribution] = Field(default_factory=list)
    stability_score: Optional[float] = None
    limitations: List[str] = Field(
        default_factory=lambda: [
            "Feature contributions describe this model's behavior for this specific input.",
            "SHAP attributions indicate feature importance to the decision, not causal ground truth.",
        ]
    )
    created_at: datetime

    class Config:
        from_attributes = True


class ExplainRequest(BaseModel):
    """Request body for POST /explain/{prediction_id}.

    All fields are optional.  If `features` is provided, the service will
    use those raw feature values for SHAP computation; otherwise it falls
    back to reconstructing from the prediction record.
    """

    features: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw feature dict {name: value} matching the model's feature schema.",
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Number of top features to return.")
    compute_stability: bool = Field(
        default=True,
        description="Whether to compute explanation stability score.",
    )
    n_repetitions: int = Field(
        default=20, ge=1, le=200, description="Stability repetitions."
    )
    noise_std: float = Field(
        default=0.05, gt=0.0, description="Gaussian noise sigma for stability perturbations."
    )


class StabilityRequest(BaseModel):
    """Request body for POST /explain/stability/{prediction_id}."""

    features: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw feature dict; if omitted uses stored zero-vector.",
    )
    n_repetitions: int = Field(default=20, ge=1, le=200)
    noise_std: float = Field(default=0.05, gt=0.0)
