"""add signal_origins and missing_signals to recommendations

Revision ID: a3c7f9e2b4d8
Revises: f4b2a9c8d6e1
Create Date: 2026-06-27 10:00:00.000000

Breakdown de fit (Briefing V4, passo 1): expoe por keyword qual sinal sustentou
cada recomendacao (setor/descricao ou evidencia) e quais sinais do catalogo
nao foram encontrados no perfil da startup.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a3c7f9e2b4d8"
down_revision = "f4b2a9c8d6e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recommendations",
        sa.Column(
            "signal_origins",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "recommendations",
        sa.Column(
            "missing_signals",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("recommendations", "missing_signals")
    op.drop_column("recommendations", "signal_origins")
