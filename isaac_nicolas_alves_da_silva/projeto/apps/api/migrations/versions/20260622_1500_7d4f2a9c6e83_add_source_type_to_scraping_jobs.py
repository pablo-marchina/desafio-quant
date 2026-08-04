"""add source_type to scraping_jobs

Revision ID: 7d4f2a9c6e83
Revises: 5b6c7d8e9f01
Create Date: 2026-06-22 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "7d4f2a9c6e83"
down_revision: str | None = "5b6c7d8e9f01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scraping_jobs",
        sa.Column(
            "source_type",
            sa.String(length=64),
            nullable=False,
            server_default="startup_evidence",
        ),
    )
    op.create_index(
        "ix_scraping_jobs_source_type",
        "scraping_jobs",
        ["source_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_scraping_jobs_source_type", table_name="scraping_jobs")
    op.drop_column("scraping_jobs", "source_type")
