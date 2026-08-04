"""add recommendations_done to url_ingestion_jobs

Revision ID: f1a2b3c4d5e6
Revises: e3f7b2a1c9d8
Create Date: 2026-06-28 11:00:00.000000

Guarda de idempotencia para o sub-passo de recommendations dentro de
ANALYZING: quando recommendations.generate() conclui, o campo e marcado
True e persistido antes de chamar briefing.generate(). Num retry pos-crash
de briefing, o use case pula recommendations e vai direto ao briefing --
evita regerar recomendacoes (RAG + LLM) desnecessariamente.
"""

from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"
down_revision = "e3f7b2a1c9d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "url_ingestion_jobs",
        sa.Column(
            "recommendations_done",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("url_ingestion_jobs", "recommendations_done")
