"""Contrato de transacao usado pelos casos de uso de scraping.

Uma Unit of Work agrupa repositorios que participam da mesma operacao. Assim,
ou todas as alteracoes sao confirmadas juntas, ou todas sao desfeitas juntas.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType

from apps.api.src.modules.scraping.domain.repositories import (
    ScrapingAttemptRepository,
    ScrapingJobRepository,
    ScrapingResultRepository,
)


class ScrapingUnitOfWork(ABC):
    """Define a fronteira de uma transacao do modulo de scraping.

    A camada de aplicacao depende deste contrato, sem conhecer AsyncSession,
    SQLAlchemy ou PostgreSQL. A implementacao concreta sera criada na camada
    de infraestrutura.
    """

    # Os tres repositorios pertencem a mesma unidade de trabalho. Na
    # implementacao PostgreSQL, eles compartilharao exatamente a mesma sessao.
    job_repository: ScrapingJobRepository
    attempt_repository: ScrapingAttemptRepository
    result_repository: ScrapingResultRepository

    @abstractmethod
    async def __aenter__(self) -> "ScrapingUnitOfWork":
        """Inicia a unidade de trabalho e disponibiliza seus repositorios."""

    @abstractmethod
    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Encerra a unidade de trabalho, desfazendo alteracoes nao confirmadas."""

    @abstractmethod
    async def commit(self) -> None:
        """Confirma todas as alteracoes realizadas na unidade de trabalho."""

    @abstractmethod
    async def rollback(self) -> None:
        """Desfaz todas as alteracoes realizadas na unidade de trabalho."""


# Os casos de uso recebem uma fabrica, e nao uma Unit of Work ja aberta. Dessa
# forma, cada execucao ganha sua propria transacao independente.
ScrapingUnitOfWorkFactory = Callable[[], ScrapingUnitOfWork]
