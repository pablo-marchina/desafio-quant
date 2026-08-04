"""add agent fields to attempts

Revision ID: d8e4a9c1b672
Revises: a41c96d32e57
Create Date: 2026-06-15 15:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e4a9c1b672"
down_revision: Union[str, None] = "a41c96d32e57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adiciona auditoria da revisao semantica com agentes."""

    op.add_column(
        "scraping_attempts",
        sa.Column("semantic_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "scraping_attempts",
        sa.Column(
            "agent_reviewed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "scraping_attempts",
        sa.Column("agent_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove os campos de auditoria de agentes."""

    op.drop_column("scraping_attempts", "agent_reason")
    op.drop_column("scraping_attempts", "agent_reviewed")
    op.drop_column("scraping_attempts", "semantic_confidence")
