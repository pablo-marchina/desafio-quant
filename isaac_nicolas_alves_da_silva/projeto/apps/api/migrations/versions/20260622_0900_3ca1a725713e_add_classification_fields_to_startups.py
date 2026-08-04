"""add classification fields to startups

Revision ID: 3ca1a725713e
Revises: 2e85accbd38f
Create Date: 2026-06-22 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "3ca1a725713e"
down_revision: str | None = "2e85accbd38f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adiciona a classificacao de maturidade de IA produzida pelo Startup Classifier Agent."""

    op.add_column(
        "startups",
        sa.Column("ai_maturity_level", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "startups",
        sa.Column("classification_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "startups",
        sa.Column(
            "classified_at", sa.DateTime(timezone=True), nullable=True
        ),
    )


def downgrade() -> None:
    """Remove os campos de classificacao de maturidade de IA."""

    op.drop_column("startups", "classified_at")
    op.drop_column("startups", "classification_reason")
    op.drop_column("startups", "ai_maturity_level")
