"""Implementacao Postgres do contrato publico IngestedDocumentReader.

Usa SQL textual para nao depender dos models/repositorios internos do
modulo (mesmo padrao de ``postgres_scraping_result_reader.py``).
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.src.database.relational.session import AsyncSessionFactory
from apps.api.src.modules.ingestion.domain.enums import DocumentSourceType
from apps.api.src.modules.ingestion.application.public.ingested_reader import (
    ChunkRecord,
    IngestedDocumentReader,
    IngestedDocumentSummary,
)

_SUMMARY_QUERY = text("""
    SELECT id, scraping_result_id, url, title, word_count, chunk_count,
           source_type, clean_text
    FROM documents
    WHERE scraping_result_id = :scraping_result_id
""")

_CHUNKS_QUERY = text("""
    SELECT c.id, c.document_id, c.text, d.url AS source_url, d.source_type
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.document_id = :document_id
    ORDER BY c.chunk_index
""")


class PostgresIngestedDocumentReader(IngestedDocumentReader):

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
    ) -> None:
        self._session_factory = session_factory

    async def get_by_scraping_result_id(
        self, scraping_result_id: UUID
    ) -> IngestedDocumentSummary | None:
        session = self._session_factory()
        try:
            result = await session.execute(
                _SUMMARY_QUERY, {"scraping_result_id": str(scraping_result_id)}
            )
            row = result.fetchone()
            if row is None:
                return None
            return IngestedDocumentSummary(
                id=row.id,
                scraping_result_id=row.scraping_result_id,
                url=row.url,
                title=row.title,
                word_count=row.word_count,
                chunk_count=row.chunk_count,
                source_type=DocumentSourceType(row.source_type),
                clean_text=row.clean_text,
            )
        finally:
            await session.close()

    async def list_chunks_by_document_id(
        self, document_id: UUID
    ) -> list[ChunkRecord]:
        session = self._session_factory()
        try:
            result = await session.execute(
                _CHUNKS_QUERY, {"document_id": str(document_id)}
            )
            return [
                ChunkRecord(
                    id=row.id,
                    document_id=row.document_id,
                    text=row.text,
                    source_url=row.source_url,
                    source_type=DocumentSourceType(row.source_type),
                )
                for row in result.fetchall()
            ]
        finally:
            await session.close()
