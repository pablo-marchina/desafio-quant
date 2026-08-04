"""create recommendation tables

Revision ID: f90193dc1578
Revises: c19a4e5f6b20
Create Date: 2026-06-21 19:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "f90193dc1578"
down_revision: str | None = "c19a4e5f6b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("technology_slug", sa.Text(), nullable=False),
        sa.Column("technology_name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("matched_keywords", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["startup_id"],
            ["startups.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recommendations_startup_id",
        "recommendations",
        ["startup_id"],
    )
    op.create_index(
        "ix_recommendations_technology_slug",
        "recommendations",
        ["technology_slug"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recommendations_technology_slug",
        table_name="recommendations",
    )
    op.drop_index(
        "ix_recommendations_startup_id",
        table_name="recommendations",
    )
    op.drop_table("recommendations")
