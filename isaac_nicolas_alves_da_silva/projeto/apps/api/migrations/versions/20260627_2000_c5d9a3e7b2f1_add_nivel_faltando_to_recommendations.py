"""add nivel and faltando to recommendations

Revision ID: c5d9a3e7b2f1
Revises: b4c8e2f1a9d7
Create Date: 2026-06-27 20:00:00.000000

Matriz de decisao por tecnologia (Briefing V4, passo 5): cada recomendacao
recebe um nivel (forte/moderada/exploratoria) derivado do score composto +
confianca, mais uma lista de sinais ausentes que elevariam ao nivel superior.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c5d9a3e7b2f1"
down_revision = "b4c8e2f1a9d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recommendations",
        sa.Column(
            "nivel",
            sa.String(16),
            nullable=False,
            server_default="exploratoria",
        ),
    )
    op.add_column(
        "recommendations",
        sa.Column(
            "faltando",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("recommendations", "faltando")
    op.drop_column("recommendations", "nivel")
