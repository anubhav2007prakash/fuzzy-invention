"""Experiment Pydantic Schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from backend.app.schemas.model_evaluation import ModelEvaluationResponse

class ExperimentCreate(BaseModel):
    name: str
    research_question: Optional[str] = None
    dataset_id: str
    model_type: str = "random_forest"
    random_seed: int = 42
    train_ratio: float = 0.8
    configuration: Dict[str, Any] = Field(default_factory=dict)

class ExperimentResponse(BaseModel):
    id: str
    name: str
    research_question: Optional[str] = None
    dataset_id: str
    model_type: str
    random_seed: int
    train_ratio: float
    status: str
    created_at: datetime
    evaluations: List[ModelEvaluationResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True
