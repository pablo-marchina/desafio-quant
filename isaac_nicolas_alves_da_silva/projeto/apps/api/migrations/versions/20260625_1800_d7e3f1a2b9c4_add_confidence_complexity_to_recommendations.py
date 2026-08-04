"""add confidence and complexity to recommendations

Revision ID: d7e3f1a2b9c4
Revises: c9d3e7f0a4b8
Create Date: 2026-06-25 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "d7e3f1a2b9c4"
down_revision = "c9d3e7f0a4b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recommendations",
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "recommendations",
        sa.Column("complexity", sa.String(length=16), nullable=False, server_default="medium"),
    )


def downgrade() -> None:
    op.drop_column("recommendations", "complexity")
    op.drop_column("recommendations", "confidence")
