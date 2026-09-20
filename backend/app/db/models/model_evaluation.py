"""Model Evaluation ORM Model."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.db.database import Base

class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    experiment_id = Column(String(36), ForeignKey("experiments.id"), nullable=False)
    model_id = Column(String(36), ForeignKey("models.id"), nullable=False)
    dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=False)
    metrics = Column(JSON, nullable=False)
    confusion_matrix = Column(JSON, nullable=True)
    execution_time_s = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    experiment = relationship("Experiment", back_populates="evaluations")
    model = relationship("ModelRecord", back_populates="evaluations")
    dataset = relationship("DatasetRecord", back_populates="evaluations")
