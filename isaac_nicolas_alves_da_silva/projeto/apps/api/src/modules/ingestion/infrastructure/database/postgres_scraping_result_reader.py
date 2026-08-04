"""Adaptador que lê scraping_results sem importar internals do módulo scraping.

Usa SQL textual para acessar a tabela `scraping_results` diretamente,
evitando qualquer dependencia dos modelos ou repositorios do modulo scraping.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.src.database.relational.session import AsyncSessionFactory
from apps.api.src.modules.ingestion.application.dto import ScrapingResultData
from apps.api.src.modules.ingestion.application.ports import ScrapingResultReader

_QUERY = text("""
    SELECT id, job_id, url, final_url, title, raw_text, quality_score, created_at
    FROM scraping_results
    WHERE id = :result_id
""")


class PostgresScrapingResultReader(ScrapingResultReader):

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
    ) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, result_id: UUID) -> ScrapingResultData | None:
        session = self._session_factory()
        try:
            result = await session.execute(_QUERY, {"result_id": str(result_id)})
            row = result.fetchone()
            if row is None:
                return None
            return ScrapingResultData(
                id=row.id,
                job_id=row.job_id,
                url=row.url,
                final_url=row.final_url,
                title=row.title,
                raw_text=row.raw_text,
                quality_score=row.quality_score,
                created_at=row.created_at,
            )
        finally:
            await session.close()
