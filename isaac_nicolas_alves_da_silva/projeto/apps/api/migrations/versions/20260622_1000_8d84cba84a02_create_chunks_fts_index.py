"""create chunks full-text search index

Revision ID: 8d84cba84a02
Revises: 3ca1a725713e
Create Date: 2026-06-22 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = "8d84cba84a02"
down_revision: str | None = "3ca1a725713e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Indice GIN de expressao para busca lexical (RAG V3) sobre chunks.text.

    Config 'simple' (sem stemming/stopwords por idioma) porque o conteudo
    coletado mistura PT-BR e ingles.
    """

    op.execute(
        "CREATE INDEX ix_chunks_text_fts ON chunks "
        "USING GIN (to_tsvector('simple', text))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_chunks_text_fts")
