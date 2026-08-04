"""Contrato transacional do modulo briefing."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType

from apps.api.src.modules.briefing.domain.repositories import BriefingRepository


class BriefingsUnitOfWork(ABC):

    briefing_repository: BriefingRepository

    @abstractmethod
    async def __aenter__(self) -> "BriefingsUnitOfWork":
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


BriefingsUnitOfWorkFactory = Callable[[], BriefingsUnitOfWork]
