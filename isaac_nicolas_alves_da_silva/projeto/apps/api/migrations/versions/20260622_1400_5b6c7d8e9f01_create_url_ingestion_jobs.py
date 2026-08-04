"""Create url_ingestion_jobs table.

Revision ID: 5b6c7d8e9f01
Revises: 2a7c9b8d1e5f
Create Date: 2026-06-22 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5b6c7d8e9f01"
down_revision: str | None = "2a7c9b8d1e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "url_ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "source_type",
            sa.String(length=64),
            server_default="startup_evidence",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scraping_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scraping_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ingestion_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("embedding_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_url_ingestion_jobs_source_type",
        "url_ingestion_jobs",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        "ix_url_ingestion_jobs_status",
        "url_ingestion_jobs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_url_ingestion_jobs_status", table_name="url_ingestion_jobs")
    op.drop_index("ix_url_ingestion_jobs_source_type", table_name="url_ingestion_jobs")
    op.drop_table("url_ingestion_jobs")
