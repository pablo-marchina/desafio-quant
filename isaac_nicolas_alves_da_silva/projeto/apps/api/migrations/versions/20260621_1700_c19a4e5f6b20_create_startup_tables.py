"""create startup tables

Revision ID: c19a4e5f6b20
Revises: b7e2c4f8a1d3
Create Date: 2026-06-21 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "c19a4e5f6b20"
down_revision: str | None = "b7e2c4f8a1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "startups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("website_url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sector", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_startups_name", "startups", ["name"])

    op.create_table(
        "startup_evidences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scraping_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["startup_id"],
            ["startups.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scraping_result_id"],
            ["scraping_results.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_startup_evidences_startup_id",
        "startup_evidences",
        ["startup_id"],
    )
    op.create_index(
        "ix_startup_evidences_scraping_result_id",
        "startup_evidences",
        ["scraping_result_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_startup_evidences_scraping_result_id",
        table_name="startup_evidences",
    )
    op.drop_index(
        "ix_startup_evidences_startup_id",
        table_name="startup_evidences",
    )
    op.drop_table("startup_evidences")

    op.drop_index("ix_startups_name", table_name="startups")
    op.drop_table("startups")
