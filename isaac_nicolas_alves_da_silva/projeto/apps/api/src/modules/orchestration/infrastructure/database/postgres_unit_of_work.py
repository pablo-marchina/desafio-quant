"""Unit of Work PostgreSQL do modulo orchestration."""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.src.database.relational.session import AsyncSessionFactory
from apps.api.src.modules.orchestration.application.unit_of_work import (
    AnalysisUnitOfWork,
)
from apps.api.src.modules.orchestration.infrastructure.database.repositories.postgres_analysis_job_repository import (
    PostgresAnalysisJobRepository,
)
from apps.api.src.modules.orchestration.infrastructure.database.repositories.postgres_url_ingestion_job_repository import (
    PostgresUrlIngestionJobRepository,
)


class PostgresAnalysisUnitOfWork(AnalysisUnitOfWork):

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
    ) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "PostgresAnalysisUnitOfWork":
        self._session = self._session_factory()
        self.analysis_job_repository = PostgresAnalysisJobRepository(self._session)
        self.url_ingestion_job_repository = PostgresUrlIngestionJobRepository(
            self._session
        )
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        await self._session.rollback()
        await self._session.close()
        self._session = None

    async def commit(self) -> None:
        await self._open_session().commit()

    async def rollback(self) -> None:
        await self._open_session().rollback()

    def _open_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError(
                "A Unit of Work deve ser usada dentro de 'async with'."
            )
        return self._session
