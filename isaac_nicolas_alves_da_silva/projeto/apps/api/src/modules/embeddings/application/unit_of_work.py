"""Contrato transacional do modulo de embeddings."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType

from apps.api.src.modules.embeddings.domain.repositories import (
    EmbeddingJobChunkRepository,
    EmbeddingJobRepository,
)


class EmbeddingsUnitOfWork(ABC):

    job_repository: EmbeddingJobRepository
    job_chunk_repository: EmbeddingJobChunkRepository

    @abstractmethod
    async def __aenter__(self) -> "EmbeddingsUnitOfWork":
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


EmbeddingsUnitOfWorkFactory = Callable[[], EmbeddingsUnitOfWork]
