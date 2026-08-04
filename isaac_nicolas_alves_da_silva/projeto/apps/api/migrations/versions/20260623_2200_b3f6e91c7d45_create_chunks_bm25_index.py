"""create chunks bm25 index (pg_search), drop old fts gin index

Revision ID: b3f6e91c7d45
Revises: 4c8a1f6e9b2d
Create Date: 2026-06-23 22:00:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = "b3f6e91c7d45"
down_revision: str | None = "4c8a1f6e9b2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Troca o full-text search nativo (ts_rank/GIN) por BM25 nativo (pg_search).

    Decisao em 23/06/2026 (Fase 3 de docs/roadmap_evolucao_tecnica_mvp.md):
    o baseline Ragas (Fase 2) mediu context_recall 0.67, considerado fraco
    o suficiente pra justificar a troca. Exige a imagem
    `paradedb/paradedb:latest-pg16` em infra/docker-compose.yml (pg_search
    nao tem binario pra Alpine/musl).

    `key_field='id'` exige UNIQUE — `chunks.id` (primary key) ja serve.
    So 1 indice bm25 por tabela; so a coluna `text` entra (a unica
    pesquisada hoje).
    """

    op.execute("DROP INDEX IF EXISTS ix_chunks_text_fts")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_search")
    op.execute(
        "CREATE INDEX ix_chunks_bm25 ON chunks "
        "USING bm25 (id, text) WITH (key_field='id')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_bm25")
    op.execute(
        "CREATE INDEX ix_chunks_text_fts ON chunks "
        "USING GIN (to_tsvector('simple', text))"
    )
