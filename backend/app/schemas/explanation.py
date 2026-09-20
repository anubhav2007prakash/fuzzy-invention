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
            "SHAP attributions indicate feature importance to the decision, not causal ground truth."
        ]
    )
    created_at: datetime

    class Config:
        from_attributes = True
