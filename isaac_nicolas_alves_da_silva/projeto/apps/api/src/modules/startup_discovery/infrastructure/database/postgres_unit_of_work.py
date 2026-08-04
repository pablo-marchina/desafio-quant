"""Unit of Work PostgreSQL do modulo startup_discovery."""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.src.database.relational.session import AsyncSessionFactory
from apps.api.src.modules.startup_discovery.domain.repositories import (
    CandidateRepository,
    DiscoveryRunRepository,
)
from apps.api.src.modules.startup_discovery.infrastructure.database.repositories.postgres_candidate_repository import (
    PostgresCandidateRepository,
)
from apps.api.src.modules.startup_discovery.infrastructure.database.repositories.postgres_discovery_run_repository import (
    PostgresDiscoveryRunRepository,
)


class PostgresDiscoveryUnitOfWork:

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
    ) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.repository: DiscoveryRunRepository
        self.candidate_repository: CandidateRepository

    async def __aenter__(self) -> "PostgresDiscoveryUnitOfWork":
        self._session = self._session_factory()
        self.repository = PostgresDiscoveryRunRepository(self._session)
        self.candidate_repository = PostgresCandidateRepository(self._session)
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
        if self._session is None:
            raise RuntimeError("Unit of Work deve ser usada dentro de 'async with'.")
        await self._session.commit()
