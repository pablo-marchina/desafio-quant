"""Unit of Work PostgreSQL do modulo agents."""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.src.database.relational.session import AsyncSessionFactory
from apps.api.src.modules.agents.application.unit_of_work import AgentsUnitOfWork
from apps.api.src.modules.agents.infrastructure.database.repositories.postgres_agent_run_repository import (
    PostgresAgentRunRepository,
)
from apps.api.src.modules.agents.infrastructure.database.repositories.postgres_agent_step_repository import (
    PostgresAgentStepRepository,
)


class PostgresAgentsUnitOfWork(AgentsUnitOfWork):
    """Controla uma transacao PostgreSQL completa dos agents."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
    ) -> None:
        self.session_factory = session_factory
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> "PostgresAgentsUnitOfWork":
        self.session = self.session_factory()
        self.run_repository = PostgresAgentRunRepository(self.session)
        self.step_repository = PostgresAgentStepRepository(self.session)
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.session is None:
            return

        await self.session.rollback()
        await self.session.close()
        self.session = None

    async def commit(self) -> None:
        await self._get_open_session().commit()

    async def rollback(self) -> None:
        await self._get_open_session().rollback()

    def _get_open_session(self) -> AsyncSession:
        if self.session is None:
            raise RuntimeError(
                "A Unit of Work deve ser usada dentro de 'async with'."
            )

        return self.session
