"""add enrichment fields to url ingestion jobs

Revision ID: f4b2a9c8d6e1
Revises: e8a7c4d2b1f9
Create Date: 2026-06-26 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f4b2a9c8d6e1"
down_revision = "e8a7c4d2b1f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "url_ingestion_jobs",
        sa.Column("parent_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "url_ingestion_jobs",
        sa.Column(
            "enrichment_round",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index(
        "ix_url_ingestion_jobs_parent_job_id",
        "url_ingestion_jobs",
        ["parent_job_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_url_ingestion_jobs_parent_job_id",
        table_name="url_ingestion_jobs",
    )
    op.drop_column("url_ingestion_jobs", "enrichment_round")
    op.drop_column("url_ingestion_jobs", "parent_job_id")
