"""Contrato transacional do modulo agents."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType

from apps.api.src.modules.agents.domain.repositories import (
    AgentRunRepository,
    AgentStepRepository,
)


class AgentsUnitOfWork(ABC):
    """Agrupa repositorios dos agents em uma mesma transacao."""

    run_repository: AgentRunRepository
    step_repository: AgentStepRepository

    @abstractmethod
    async def __aenter__(self) -> "AgentsUnitOfWork":
        """Inicia a unidade de trabalho."""

    @abstractmethod
    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Encerra a unidade de trabalho."""

    @abstractmethod
    async def commit(self) -> None:
        """Confirma alteracoes."""

    @abstractmethod
    async def rollback(self) -> None:
        """Desfaz alteracoes."""


AgentsUnitOfWorkFactory = Callable[[], AgentsUnitOfWork]
