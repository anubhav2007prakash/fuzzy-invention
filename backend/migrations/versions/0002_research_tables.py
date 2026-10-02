"""research tables — analyst reviews + experiment collaboration

Revision ID: 0002_research
Revises: 0001_initial
Create Date: 2026-09-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_research"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analyst_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("prediction_id", sa.String(36), sa.ForeignKey("predictions.id"), nullable=False),
        sa.Column("model_id", sa.String(36), nullable=True),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("model_predicted_class", sa.String(50), nullable=False),
        sa.Column("human_decision", sa.String(20), nullable=False),
        sa.Column("analyst", sa.String(120), nullable=False, server_default="analyst"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("audit_record_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_analyst_reviews_prediction_id", "analyst_reviews", ["prediction_id"])
    op.create_index("ix_analyst_reviews_decision", "analyst_reviews", ["human_decision"])

    op.create_table(
        "experiment_comments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("experiment_id", sa.String(50), nullable=False),
        sa.Column("author", sa.String(120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_experiment_comments_experiment_id", "experiment_comments", ["experiment_id"])

    op.create_table(
        "experiment_review_states",
        sa.Column("experiment_id", sa.String(50), primary_key=True),
        sa.Column("owner", sa.String(120), nullable=True),
        sa.Column("review_status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("reviewers_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("approved_by", sa.String(120), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("experiment_review_states")
    op.drop_index("ix_experiment_comments_experiment_id", table_name="experiment_comments")
    op.drop_table("experiment_comments")
    op.drop_index("ix_analyst_reviews_decision", table_name="analyst_reviews")
    op.drop_index("ix_analyst_reviews_prediction_id", table_name="analyst_reviews")
    op.drop_table("analyst_reviews")
