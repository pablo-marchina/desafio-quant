"""add structured fields to startups

Revision ID: f77998c46d08
Revises: 8d84cba84a02
Create Date: 2026-06-22 11:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "f77998c46d08"
down_revision: str | None = "8d84cba84a02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adiciona founders/funding/customers (Startups V2)."""

    op.add_column(
        "startups",
        sa.Column(
            "founders",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "startups",
        sa.Column("funding_stage", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "startups",
        sa.Column("funding_amount_usd", sa.Float(), nullable=True),
    )
    op.add_column(
        "startups",
        sa.Column(
            "customers",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("startups", "customers")
    op.drop_column("startups", "funding_amount_usd")
    op.drop_column("startups", "funding_stage")
    op.drop_column("startups", "founders")
