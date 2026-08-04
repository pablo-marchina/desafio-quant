"""Contrato transacional do modulo startups."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType

from apps.api.src.modules.startups.domain.repositories import (
    StartupEvidenceRepository,
    StartupRepository,
)


class StartupsUnitOfWork(ABC):

    startup_repository: StartupRepository
    evidence_repository: StartupEvidenceRepository

    @abstractmethod
    async def __aenter__(self) -> "StartupsUnitOfWork":
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


StartupsUnitOfWorkFactory = Callable[[], StartupsUnitOfWork]
