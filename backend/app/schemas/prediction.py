"""Prediction Pydantic Schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field

class PredictionRequest(BaseModel):
    model_id: str
    features: Dict[str, Union[float, int, str]]
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0,
        description="Minimum probability threshold. Below this, predicted_class is 'UNCERTAIN'.")

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
    confidence: Optional[float] = None
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
