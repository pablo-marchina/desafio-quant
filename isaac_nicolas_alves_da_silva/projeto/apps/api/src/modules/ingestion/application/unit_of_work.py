"""Contrato transacional do módulo de ingestion."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType

from apps.api.src.modules.ingestion.domain.repositories import (
    ChunkRepository,
    DocumentRepository,
    IngestionJobRepository,
)


class IngestionUnitOfWork(ABC):

    job_repository: IngestionJobRepository
    document_repository: DocumentRepository
    chunk_repository: ChunkRepository

    @abstractmethod
    async def __aenter__(self) -> "IngestionUnitOfWork":
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


IngestionUnitOfWorkFactory = Callable[[], IngestionUnitOfWork]
