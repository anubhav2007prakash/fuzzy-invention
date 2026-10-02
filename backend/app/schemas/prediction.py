"""Prediction Pydantic Schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field

class PredictionRequest(BaseModel):
    model_id: str
    features: Dict[str, Union[float, int, str]]
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0,
        description="Legacy-named minimum maximum-class-probability threshold. Below it, predicted_class is 'UNCERTAIN'; this threshold is not a real-world confidence guarantee.")

class BatchPredictionRequest(BaseModel):
    model_id: str
    samples: List[Dict[str, Union[float, int, str]]]

class PredictionResponse(BaseModel):
    prediction_id: str
    model_id: str
    model_version: str
    predicted_class: str
    prediction_label: int
    probabilities: Optional[Dict[str, float]] = None
    confidence: Optional[float] = Field(
        None,
        description="Legacy alias for the maximum class probability when thresholding is requested; not a guarantee of real-world confidence.",
    )
    is_uncertain: bool = False
    input_hash: str
    latency_ms: float
    created_at: datetime

    class Config:
        from_attributes = True

class BatchPredictionResponse(BaseModel):
    total_samples: int
    predictions: List[PredictionResponse]
    processing_time_ms: float
