"""Implementacao PostgreSQL da Unit of Work do modulo de scraping."""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.src.database.relational.session import AsyncSessionFactory
from apps.api.src.modules.scraping.application.unit_of_work import (
    ScrapingUnitOfWork,
)
from apps.api.src.modules.scraping.infrastructure.database.repositories.postgres_attempt_repository import (
    PostgresScrapingAttemptRepository,
)
from apps.api.src.modules.scraping.infrastructure.database.repositories.postgres_job_repository import (
    PostgresScrapingJobRepository,
)
from apps.api.src.modules.scraping.infrastructure.database.repositories.postgres_result_repository import (
    PostgresScrapingResultRepository,
)


class PostgresScrapingUnitOfWork(ScrapingUnitOfWork):
    """Controla uma transacao PostgreSQL completa do modulo de scraping.

    Cada instancia abre sua propria AsyncSession. Os tres repositorios recebem
    essa mesma sessao, portanto todas as alteracoes pertencem a uma unica
    transacao.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
    ) -> None:
        # Receber a factory por parametro facilita testes e permite trocar a
        # configuracao da sessao sem alterar esta classe.
        self.session_factory = session_factory
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> "PostgresScrapingUnitOfWork":
        """Abre a sessao e cria repositorios que compartilham essa sessao."""

        self.session = self.session_factory()

        self.job_repository = PostgresScrapingJobRepository(self.session)
        self.attempt_repository = PostgresScrapingAttemptRepository(self.session)
        self.result_repository = PostgresScrapingResultRepository(self.session)

        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Desfaz alteracoes pendentes e fecha a sessao ao sair do contexto."""

        if self.session is None:
            return

        # Mesmo depois de um commit, rollback e seguro e garante que qualquer
        # nova alteracao acidental feita depois dele nao seja persistida.
        await self.session.rollback()
        await self.session.close()
        self.session = None

    async def commit(self) -> None:
        """Confirma todas as alteracoes feitas pelos repositorios."""

        await self._get_open_session().commit()

    async def rollback(self) -> None:
        """Desfaz todas as alteracoes ainda nao confirmadas."""

        await self._get_open_session().rollback()

    def _get_open_session(self) -> AsyncSession:
        """Retorna a sessao aberta ou denuncia uso fora do contexto."""

        if self.session is None:
            raise RuntimeError(
                "A Unit of Work deve ser usada dentro de 'async with'."
            )

        return self.session
