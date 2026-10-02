"""Model Pydantic Schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

class ModelTrainRequest(BaseModel):
    dataset_id: str
    model_type: str = Field("random_forest", description="'logistic_regression' or 'random_forest'")
    experiment_id: Optional[str] = None
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    random_seed: int = 42
    train_ratio: float = 0.8
    calibration_method: Optional[Literal["sigmoid", "isotonic"]] = Field(
        None,
        description="Optional post-hoc binary probability calibration fitted on a reserved training subset.",
    )
    calibration_fraction: float = Field(
        0.2,
        gt=0,
        lt=0.5,
        description="Fraction of the model-training partition reserved for calibration when enabled.",
    )

class ModelResponse(BaseModel):
    id: str
    experiment_id: Optional[str] = None
    name: str
    version: str
    artifact_path: str
    preprocessing_path: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    calibration: Dict[str, Any] = Field(default_factory=dict)
    feature_schema: List[Dict[str, str]] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True

class ModelMetricsResponse(BaseModel):
    model_id: str
    model_name: str
    version: str
    metrics: Dict[str, Any]
    calibration: Dict[str, Any] = Field(default_factory=dict)
    confusion_matrix: Optional[Dict[str, Any]] = None
    classification_report: Optional[Dict[str, Any]] = None
