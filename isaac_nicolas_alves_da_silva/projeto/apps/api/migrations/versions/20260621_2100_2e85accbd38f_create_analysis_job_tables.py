"""create analysis job tables

Revision ID: 2e85accbd38f
Revises: 782e2cbdbfab
Create Date: 2026-06-21 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "2e85accbd38f"
down_revision: str | None = "782e2cbdbfab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("recommendation_count", sa.Integer(), nullable=True),
        sa.Column("briefing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["startup_id"],
            ["startups.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_jobs_startup_id",
        "analysis_jobs",
        ["startup_id"],
    )
    op.create_index(
        "ix_analysis_jobs_status",
        "analysis_jobs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_analysis_jobs_status",
        table_name="analysis_jobs",
    )
    op.drop_index(
        "ix_analysis_jobs_startup_id",
        table_name="analysis_jobs",
    )
    op.drop_table("analysis_jobs")
