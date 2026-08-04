"""add source_type to ingestion_jobs

Revision ID: 2a7c9b8d1e5f
Revises: 1d3e7f9a2b4c
Create Date: 2026-06-22 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "2a7c9b8d1e5f"
down_revision: str | None = "1d3e7f9a2b4c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "source_type",
            sa.String(length=64),
            nullable=False,
            server_default="startup_evidence",
        ),
    )
    op.create_index(
        "ix_ingestion_jobs_source_type",
        "ingestion_jobs",
        ["source_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_source_type", table_name="ingestion_jobs")
    op.drop_column("ingestion_jobs", "source_type")
