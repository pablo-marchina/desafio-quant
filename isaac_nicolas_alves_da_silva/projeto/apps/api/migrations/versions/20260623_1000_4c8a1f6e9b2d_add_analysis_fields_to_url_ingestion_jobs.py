"""add analysis fields to url_ingestion_jobs

Revision ID: 4c8a1f6e9b2d
Revises: 7d4f2a9c6e83
Create Date: 2026-06-23 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "4c8a1f6e9b2d"
down_revision: str | None = "7d4f2a9c6e83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "url_ingestion_jobs",
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "url_ingestion_jobs",
        sa.Column(
            "evidence_attached",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "url_ingestion_jobs",
        sa.Column("recommendation_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "url_ingestion_jobs",
        sa.Column("briefing_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_url_ingestion_jobs_startup_id",
        "url_ingestion_jobs",
        "startups",
        ["startup_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_url_ingestion_jobs_startup_id",
        "url_ingestion_jobs",
        ["startup_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_url_ingestion_jobs_startup_id", table_name="url_ingestion_jobs"
    )
    op.drop_constraint(
        "fk_url_ingestion_jobs_startup_id",
        "url_ingestion_jobs",
        type_="foreignkey",
    )
    op.drop_column("url_ingestion_jobs", "briefing_id")
    op.drop_column("url_ingestion_jobs", "recommendation_count")
    op.drop_column("url_ingestion_jobs", "evidence_attached")
    op.drop_column("url_ingestion_jobs", "startup_id")
