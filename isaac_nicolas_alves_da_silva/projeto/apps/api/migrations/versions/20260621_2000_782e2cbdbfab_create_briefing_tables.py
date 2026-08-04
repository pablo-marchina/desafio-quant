"""create briefing tables

Revision ID: 782e2cbdbfab
Revises: f90193dc1578
Create Date: 2026-06-21 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "782e2cbdbfab"
down_revision: str | None = "f90193dc1578"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "briefings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("startup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["startup_id"],
            ["startups.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_briefings_startup_id",
        "briefings",
        ["startup_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_briefings_startup_id",
        table_name="briefings",
    )
    op.drop_table("briefings")
