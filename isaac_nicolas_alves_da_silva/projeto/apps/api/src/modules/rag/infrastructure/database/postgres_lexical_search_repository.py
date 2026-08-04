"""Adaptador que le `chunks` (de `ingestion`) sem importar internals do modulo.

Usa SQL textual contra a tabela `chunks` para fazer busca lexical via BM25
nativo (extensao `pg_search`/ParadeDB), evitando qualquer dependencia dos
modelos ou repositorios do modulo ingestion. Mesmo padrao de
`ingestion/infrastructure/database/postgres_scraping_result_reader.py`
(que le `scraping_results` da mesma forma).

Trocado de `to_tsvector('simple')`/`ts_rank` pra BM25 em 23/06/2026 (Fase 3
de docs/roadmap_evolucao_tecnica_mvp.md — baseline Ragas mediu
context_recall 0.67, considerado fraco). Indice `ix_chunks_bm25`
(`USING bm25 (id, text)`) criado na migration `b3f6e91c7d45` — exige a
extensao `pg_search` e a imagem `paradedb/paradedb:latest-pg16` em
`infra/docker-compose.yml` (pg_search nao tem binario pra Alpine/musl).
Operador `@@@` e `paradedb.score()` confirmados testando direto contra um
container real antes de escrever esta versao (ver
docs/rag/roadmap_rag.md).
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.src.database.relational.session import AsyncSessionFactory
from apps.api.src.modules.rag.application.dto import LexicalSearchResult
from apps.api.src.modules.rag.application.ports import LexicalSearchRepository

_BASE_SQL = """
    SELECT c.id, c.document_id, paradedb.score(c.id) AS rank
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.text @@@ :query
"""


class PostgresLexicalSearchRepository(LexicalSearchRepository):

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
    ) -> None:
        self._session_factory = session_factory

    async def search(
        self,
        query: str,
        *,
        limit: int,
        source_type: str | None = None,
        document_ids: list[UUID] | None = None,
    ) -> list[LexicalSearchResult]:
        if document_ids is not None and len(document_ids) == 0:
            return []

        params: dict = {"query": query, "limit": limit}
        extra_clauses: list[str] = []

        if source_type is not None:
            extra_clauses.append("d.source_type = :source_type")
            params["source_type"] = source_type

        if document_ids is not None:
            placeholders = ", ".join(f":did_{i}" for i in range(len(document_ids)))
            extra_clauses.append(f"c.document_id IN ({placeholders})")
            for i, did in enumerate(document_ids):
                params[f"did_{i}"] = did

        where_suffix = ""
        if extra_clauses:
            where_suffix = " AND " + " AND ".join(extra_clauses)

        sql = text(
            _BASE_SQL + where_suffix + "\n    ORDER BY rank DESC\n    LIMIT :limit"
        )

        session = self._session_factory()
        try:
            result = await session.execute(sql, params)
            return [
                LexicalSearchResult(
                    chunk_id=row.id,
                    document_id=row.document_id,
                    score=row.rank,
                )
                for row in result.fetchall()
            ]
        finally:
            await session.close()
