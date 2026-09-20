"""Model Evaluation Repository."""
import json
from typing import List, Optional
from sqlalchemy.orm import Session
from backend.app.db.models import ModelEvaluation
from backend.app.schemas.model_evaluation import ModelEvaluationCreate


class ModelEvaluationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, obj_in: ModelEvaluationCreate) -> ModelEvaluation:
        metrics_str = json.dumps(obj_in.metrics) if isinstance(obj_in.metrics, dict) else str(obj_in.metrics)
        cm_str = (
            json.dumps(obj_in.confusion_matrix)
            if isinstance(obj_in.confusion_matrix, dict)
            else (str(obj_in.confusion_matrix) if obj_in.confusion_matrix else None)
        )
        db_obj = ModelEvaluation(
            experiment_id=obj_in.experiment_id,
            model_id=obj_in.model_id,
            dataset_id=obj_in.dataset_id,
            metrics_json=metrics_str,
            confusion_matrix_json=cm_str,
            execution_time_s=obj_in.execution_time_s,
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get_by_id(self, evaluation_id: str) -> Optional[ModelEvaluation]:
        return self.db.query(ModelEvaluation).filter(ModelEvaluation.id == evaluation_id).first()

    def get_by_experiment(self, experiment_id: str) -> List[ModelEvaluation]:
        return self.db.query(ModelEvaluation).filter(ModelEvaluation.experiment_id == experiment_id).all()

    def get_by_model(self, model_id: str) -> List[ModelEvaluation]:
        return self.db.query(ModelEvaluation).filter(ModelEvaluation.model_id == model_id).all()
