import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _uuid() -> str:
    return str(uuid.uuid4())


class FalsificationExperiment(Base):
    """A researcher-defined claim to attempt to disprove, with configuration for baseline,
    alternative, perturbation, and repeated runs."""

    __tablename__ = "falsification_experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    research_question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Claim identification
    claim_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    claim_statement: Mapped[str] = mapped_column(Text, nullable=False)

    # Configuration groups
    baseline_configuration: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    alternative_configuration: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    alternative_dataset_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("datasets.id"), nullable=True
    )  # FK to datasets

    # Controlled perturbation settings
    perturbation_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "gaussian_noise", "feature_dropout"
    perturbation_strength: Mapped[Optional[float]] = mapped_column(nullable=True)
    perturbation_distribution: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., "normal", "uniform"

    # Repeated runs
    n_repeats: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, default=42, nullable=False)

    # Status and acceptance
    acceptance_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    conclusion_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # SUPPORTED / PARTIALLY_SUPPORTED / NOT_SUPPORTED / INCONCLUSIVE

    # Metadata
    configuration_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA-256
    result_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA-256
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    dataset = relationship("Dataset", back_populates="falsification_experiments", cascade="all")
    results = relationship("FalsificationResult", back_populates="experiment", cascade="all, delete-orphan")


class FalsificationResult(Base):
    """Raw results and derived metrics from one falsification run configuration."""

    __tablename__ = "falsification_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    experiment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("falsification_experiments.id"), nullable=False
    )
    run_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Which repeat (0-indexed)
    configuration_snapshot: Mapped[str] = mapped_column(Text, nullable=False)  # JSON

    # Raw results
    raw_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    provenance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    # Derived metrics
    derived_metrics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    statistical_test: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "t-test", "chi-squared"
    statistical_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    # Plots (file paths stored as JSON array)
    plots: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of file paths

    # Evidence
    evidence_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    # Conclusion
    conclusion_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # SUPPORTED / PARTIALLY_SUPPORTED / NOT_SUPPORTED / INCONCLUSIVE
    conclusion_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Reproducibility metadata
    reproducibility_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    # Timing
    execution_time_s: Mapped[float] = mapped_column(default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    # Relationships
    experiment = relationship("FalsificationExperiment", back_populates="results")


# Alias for backward compatibility / easy import
Experiment = FalsificationExperiment
Result = FalsificationResult