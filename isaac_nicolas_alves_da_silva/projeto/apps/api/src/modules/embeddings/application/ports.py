"""Portas (interfaces) do modulo de embeddings."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.embeddings.application.dto import ChunkSourceItem


class ChunkSourceReader(ABC):
    """Porta para ler chunks de documentos ja ingeridos, sem importar internals do modulo ingestion."""

    @abstractmethod
    async def list_chunks(self, document_id: UUID) -> list[ChunkSourceItem]:
        """Retorna os chunks de um documento, prontos para embedding."""


class EmbeddingTaskDispatcher(ABC):
    """Porta para publicar jobs de embeddings na fila."""

    @abstractmethod
    async def dispatch(self, *, job_id: UUID) -> None:
        """Publica o job_id na fila de embeddings."""
