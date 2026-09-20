"""SQLAlchemy ORM Models — single authoritative source for SentinelCrypt AI."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer,
    String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # store as UTC, tz-naive


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# Dataset
# ─────────────────────────────────────────────────────────────────────────────

class Dataset(Base):
    __tablename__ = "datasets"

    id:                Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    name:              Mapped[str]           = mapped_column(String(255), nullable=False)
    source:            Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_name:         Mapped[str]           = mapped_column(String(255), nullable=False)
    file_hash:         Mapped[str]           = mapped_column(String(64),  nullable=False)  # SHA-256
    row_count:         Mapped[int]           = mapped_column(Integer, nullable=False, default=0)
    feature_count:     Mapped[int]           = mapped_column(Integer, nullable=False, default=0)
    target_column:     Mapped[str]           = mapped_column(String(255), nullable=False, default="label")
    validation_status: Mapped[str]           = mapped_column(String(50),  nullable=False, default="VALID")
    label_distribution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    created_at:        Mapped[datetime]      = mapped_column(DateTime, default=_utcnow, nullable=False)

    features    = relationship("DatasetFeature", back_populates="dataset", cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="dataset")


class DatasetFeature(Base):
    __tablename__ = "dataset_features"

    id:            Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id:    Mapped[str]           = mapped_column(String(36), ForeignKey("datasets.id"), nullable=False)
    feature_name:  Mapped[str]           = mapped_column(String(255), nullable=False)
    data_type:     Mapped[str]           = mapped_column(String(50),  nullable=False)
    is_selected:   Mapped[bool]          = mapped_column(Boolean, default=True, nullable=False)
    missing_count: Mapped[int]           = mapped_column(Integer, default=0, nullable=False)

    dataset = relationship("Dataset", back_populates="features")


# ─────────────────────────────────────────────────────────────────────────────
# Experiment
# ─────────────────────────────────────────────────────────────────────────────

class Experiment(Base):
    __tablename__ = "experiments"

    id:                 Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    name:               Mapped[str]           = mapped_column(String(100), nullable=False)
    research_question:  Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dataset_id:         Mapped[str]           = mapped_column(String(36), ForeignKey("datasets.id"), nullable=False)
    model_type:         Mapped[str]           = mapped_column(String(50),  nullable=False)
    random_seed:        Mapped[int]           = mapped_column(Integer, default=42, nullable=False)
    train_ratio:        Mapped[float]         = mapped_column(Float, default=0.8, nullable=False)
    configuration_json: Mapped[str]          = mapped_column(Text, nullable=False, default="{}")
    status:             Mapped[str]          = mapped_column(String(50), default="pending", nullable=False)
    created_at:         Mapped[datetime]     = mapped_column(DateTime, default=_utcnow, nullable=False)

    dataset   = relationship("Dataset", back_populates="experiments")
    models    = relationship("ModelRecord", back_populates="experiment")
    evaluations = relationship("ModelEvaluation", back_populates="experiment")


# ─────────────────────────────────────────────────────────────────────────────
# Model
# ─────────────────────────────────────────────────────────────────────────────

class ModelRecord(Base):
    __tablename__ = "models"

    id:                  Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    experiment_id:       Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("experiments.id"), nullable=True)
    name:                Mapped[str]           = mapped_column(String(100), nullable=False)
    version:             Mapped[str]           = mapped_column(String(50),  nullable=False, default="v1.0.0")
    artifact_path:       Mapped[str]           = mapped_column(String(500), nullable=False)
    preprocessing_path:  Mapped[str]           = mapped_column(String(500), nullable=False)
    metrics_json:        Mapped[str]           = mapped_column(Text, nullable=False, default="{}")
    feature_schema_json: Mapped[str]           = mapped_column(Text, nullable=False, default="[]")
    created_at:          Mapped[datetime]      = mapped_column(DateTime, default=_utcnow, nullable=False)

    experiment  = relationship("Experiment", back_populates="models")
    predictions = relationship("Prediction", back_populates="model")
    evaluations = relationship("ModelEvaluation", back_populates="model")


# ─────────────────────────────────────────────────────────────────────────────
# Prediction
# ─────────────────────────────────────────────────────────────────────────────

class Prediction(Base):
    __tablename__ = "predictions"

    id:              Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    model_id:        Mapped[str]           = mapped_column(String(36), ForeignKey("models.id"), nullable=False)
    input_hash:      Mapped[str]           = mapped_column(String(64),  nullable=False)
    predicted_class: Mapped[str]           = mapped_column(String(50),  nullable=False)
    probabilities_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_source:  Mapped[str]           = mapped_column(String(100), default="api", nullable=False)
    latency_ms:      Mapped[float]         = mapped_column(Float, default=0.0, nullable=False)
    created_at:      Mapped[datetime]      = mapped_column(DateTime, default=_utcnow, nullable=False)

    model        = relationship("ModelRecord", back_populates="predictions")
    explanation  = relationship("Explanation",  back_populates="prediction", uselist=False, cascade="all, delete-orphan")
    audit_record = relationship("AuditRecord",  back_populates="prediction", uselist=False, cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────────────
# Explanation
# ─────────────────────────────────────────────────────────────────────────────

class Explanation(Base):
    __tablename__ = "explanations"

    id:                  Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    prediction_id:       Mapped[str]           = mapped_column(String(36), ForeignKey("predictions.id"), unique=True, nullable=False)
    method:              Mapped[str]           = mapped_column(String(50),  nullable=False, default="SHAP")
    top_features_json:   Mapped[str]           = mapped_column(Text, nullable=False, default="[]")
    base_value:          Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    explanation_version: Mapped[str]           = mapped_column(String(50),  nullable=False, default="v1.0")
    stability_score:     Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at:          Mapped[datetime]      = mapped_column(DateTime, default=_utcnow, nullable=False)

    prediction = relationship("Prediction", back_populates="explanation")


# ─────────────────────────────────────────────────────────────────────────────
# AuditRecord (Cryptographic Hash Chain)
# ─────────────────────────────────────────────────────────────────────────────

class AuditRecord(Base):
    __tablename__ = "audit_records"
    __table_args__ = (UniqueConstraint("sequence_number"),)

    id:              Mapped[str]      = mapped_column(String(36), primary_key=True, default=_uuid)
    sequence_number: Mapped[int]     = mapped_column(Integer, nullable=False)
    prediction_id:   Mapped[str]     = mapped_column(String(36), ForeignKey("predictions.id"), unique=True, nullable=False)
    payload_json:    Mapped[str]     = mapped_column(Text, nullable=False)   # canonical evidence
    previous_hash:   Mapped[str]     = mapped_column(String(64), nullable=False)
    record_hash:     Mapped[str]     = mapped_column(String(64), nullable=False)
    created_at:      Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    prediction = relationship("Prediction", back_populates="audit_record")


# ─────────────────────────────────────────────────────────────────────────────
# ModelEvaluation (Experiment sub-results)
# ─────────────────────────────────────────────────────────────────────────────

class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"

    id:               Mapped[str]   = mapped_column(String(36), primary_key=True, default=_uuid)
    experiment_id:    Mapped[str]   = mapped_column(String(36), ForeignKey("experiments.id"), nullable=False)
    model_id:         Mapped[str]   = mapped_column(String(36), ForeignKey("models.id"), nullable=False)
    dataset_id:       Mapped[str]   = mapped_column(String(36), ForeignKey("datasets.id"), nullable=False)
    metrics_json:     Mapped[str]   = mapped_column(Text, nullable=False, default="{}")
    confusion_matrix_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at:       Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    experiment = relationship("Experiment",  back_populates="evaluations")
    model      = relationship("ModelRecord", back_populates="evaluations")
    dataset    = relationship("Dataset")
