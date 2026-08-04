"""create opportunity_score_records table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-13 18:40:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "opportunity_score_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("score_version", sa.Integer(), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("score_tier", sa.String(length=30), nullable=False),
        sa.Column("components_json", sa.JSON(), nullable=False),
        sa.Column("penalties_json", sa.JSON(), nullable=False),
        sa.Column("penalty_total", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("evidence_refs_json", sa.JSON(), nullable=False),
        sa.Column("recommended_action", sa.String(length=255), nullable=False, default=""),
        sa.Column("reasoning", sa.Text(), nullable=False, default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_opportunity_score_run_version",
        "opportunity_score_records",
        ["analysis_run_id", "score_version"],
        unique=False,
    )
    op.create_index(
        "ix_opportunity_score_score",
        "opportunity_score_records",
        ["opportunity_score"],
        unique=False,
    )
    op.create_index(
        "ix_opportunity_score_tier",
        "opportunity_score_records",
        ["score_tier"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_opportunity_score_tier", table_name="opportunity_score_records")
    op.drop_index("ix_opportunity_score_score", table_name="opportunity_score_records")
    op.drop_index("ix_opportunity_score_run_version", table_name="opportunity_score_records")
    op.drop_table("opportunity_score_records")
