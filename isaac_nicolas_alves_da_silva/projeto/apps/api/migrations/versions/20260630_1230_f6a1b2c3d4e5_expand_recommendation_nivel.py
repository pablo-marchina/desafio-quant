"""expand recommendation nivel length

Revision ID: f6a1b2c3d4e5
Revises: b5f2a1c8d9e7
Create Date: 2026-06-30 12:30:00.000000

``hipotese_prioritaria`` tem 20 caracteres e nao cabia no ``String(16)``
original, fazendo a analise falhar ao persistir recomendacoes qualificadas.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f6a1b2c3d4e5"
down_revision: str | None = "b5f2a1c8d9e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "recommendations",
        "nivel",
        existing_type=sa.String(16),
        type_=sa.String(32),
        existing_nullable=False,
        existing_server_default="exploratoria",
    )


def downgrade() -> None:
    op.alter_column(
        "recommendations",
        "nivel",
        existing_type=sa.String(32),
        type_=sa.String(16),
        existing_nullable=False,
        existing_server_default="exploratoria",
    )
