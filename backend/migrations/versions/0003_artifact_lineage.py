"""Persist cryptographic research artifact lineage.

Revision ID: 0003_lineage
Revises: 0002_research
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_lineage"
down_revision: Union[str, None] = "0002_research"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "artifact_lineage",
        sa.Column("artifact_id", sa.String(length=160), primary_key=True),
        sa.Column("artifact_type", sa.String(length=50), nullable=False),
        sa.Column(
            "parent_artifact_id",
            sa.String(length=160),
            sa.ForeignKey("artifact_lineage.artifact_id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("git_commit", sa.String(length=64), nullable=True),
        sa.Column("experiment_id", sa.String(length=100), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index(
        "ix_artifact_lineage_parent_artifact_id",
        "artifact_lineage",
        ["parent_artifact_id"],
    )
    op.create_index(
        "ix_artifact_lineage_experiment_id",
        "artifact_lineage",
        ["experiment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_lineage_experiment_id", table_name="artifact_lineage")
    op.drop_index("ix_artifact_lineage_parent_artifact_id", table_name="artifact_lineage")
    op.drop_table("artifact_lineage")
