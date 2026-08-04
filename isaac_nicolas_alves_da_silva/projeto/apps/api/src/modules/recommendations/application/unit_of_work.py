"""Contrato transacional do modulo recommendations."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType

from apps.api.src.modules.recommendations.domain.repositories import (
    RecommendationRepository,
)


class RecommendationsUnitOfWork(ABC):

    recommendation_repository: RecommendationRepository

    @abstractmethod
    async def __aenter__(self) -> "RecommendationsUnitOfWork":
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


RecommendationsUnitOfWorkFactory = Callable[[], RecommendationsUnitOfWork]
