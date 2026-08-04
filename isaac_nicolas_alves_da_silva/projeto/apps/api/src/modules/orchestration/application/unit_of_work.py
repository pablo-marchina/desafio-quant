"""Contrato transacional do modulo orchestration."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType

from apps.api.src.modules.orchestration.domain.repositories import (
    AnalysisJobRepository,
    UrlIngestionJobRepository,
)


class AnalysisUnitOfWork(ABC):

    analysis_job_repository: AnalysisJobRepository
    url_ingestion_job_repository: UrlIngestionJobRepository

    @abstractmethod
    async def __aenter__(self) -> "AnalysisUnitOfWork":
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


AnalysisUnitOfWorkFactory = Callable[[], AnalysisUnitOfWork]
