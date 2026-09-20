"""Model Evaluation Pydantic Schemas."""
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class ModelEvaluationBase(BaseModel):
    experiment_id: str
    model_id: str
    dataset_id: str
    metrics: Dict[str, float] = Field(..., description="Evaluation metrics: accuracy, precision, recall, f1, etc.")
    confusion_matrix: Optional[Dict[str, Any]] = None
    execution_time_s: float = 0.0

class ModelEvaluationCreate(ModelEvaluationBase):
    pass

class ModelEvaluationResponse(ModelEvaluationBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True
