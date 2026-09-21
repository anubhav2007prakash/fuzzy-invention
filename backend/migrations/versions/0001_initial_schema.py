"""initial schema — full CREATE TABLE + indexes

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── datasets ─────────────────────────────────────────────────────────────
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source", sa.String(500), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("feature_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_column", sa.String(255), nullable=False, server_default="label"),
        sa.Column("validation_status", sa.String(50), nullable=False, server_default="VALID"),
        sa.Column("label_distribution", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_datasets_file_hash", "datasets", ["file_hash"], unique=True)

    # ── dataset_features ──────────────────────────────────────────────────────
    op.create_table(
        "dataset_features",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("feature_name", sa.String(255), nullable=False),
        sa.Column("data_type", sa.String(50), nullable=False),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("missing_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # ── experiments ───────────────────────────────────────────────────────────
    op.create_table(
        "experiments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("research_question", sa.Text(), nullable=True),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("model_type", sa.String(50), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False, server_default="42"),
        sa.Column("train_ratio", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("configuration_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_experiments_dataset_id", "experiments", ["dataset_id"])
    op.create_index("ix_experiments_status", "experiments", ["status"])

    # ── models ────────────────────────────────────────────────────────────────
    op.create_table(
        "models",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("experiment_id", sa.String(36), sa.ForeignKey("experiments.id"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(50), nullable=False, server_default="v1.0.0"),
        sa.Column("artifact_path", sa.String(500), nullable=False),
        sa.Column("preprocessing_path", sa.String(500), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("feature_schema_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # ── predictions ───────────────────────────────────────────────────────────
    op.create_table(
        "predictions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model_id", sa.String(36), sa.ForeignKey("models.id"), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("predicted_class", sa.String(50), nullable=False),
        sa.Column("probabilities_json", sa.Text(), nullable=True),
        sa.Column("request_source", sa.String(100), nullable=False, server_default="api"),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # ── explanations ──────────────────────────────────────────────────────────
    op.create_table(
        "explanations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("prediction_id", sa.String(36), sa.ForeignKey("predictions.id"), unique=True, nullable=False),
        sa.Column("method", sa.String(50), nullable=False, server_default="SHAP"),
        sa.Column("top_features_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("base_value", sa.Float(), nullable=True),
        sa.Column("explanation_version", sa.String(50), nullable=False, server_default="v1.0"),
        sa.Column("stability_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # ── audit_records ─────────────────────────────────────────────────────────
    op.create_table(
        "audit_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("prediction_id", sa.String(36), sa.ForeignKey("predictions.id"), unique=True, nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("sequence_number"),
    )
    op.create_index("ix_audit_records_sequence", "audit_records", ["sequence_number"])

    # ── model_evaluations ─────────────────────────────────────────────────────
    op.create_table(
        "model_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("experiment_id", sa.String(36), sa.ForeignKey("experiments.id"), nullable=False),
        sa.Column("model_id", sa.String(36), sa.ForeignKey("models.id"), nullable=False),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("confusion_matrix_json", sa.Text(), nullable=True),
        sa.Column("execution_time_s", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_model_evaluations_experiment_id", "model_evaluations", ["experiment_id"])
    op.create_index("ix_model_evaluations_model_id", "model_evaluations", ["model_id"])


def downgrade() -> None:
    op.drop_table("model_evaluations")
    op.drop_table("audit_records")
    op.drop_table("explanations")
    op.drop_table("predictions")
    op.drop_table("models")
    op.drop_table("experiments")
    op.drop_table("dataset_features")
    op.drop_table("datasets")
