"""Contrato publico de persistencia e busca vetorial.

Outro arquivo que outros modulos (ex: RAG) podem importar diretamente — o
RAG vai chamar ``search()`` para recuperar chunks semanticamente
relevantes. ``upsert()`` e usado internamente pelo proprio modulo
embeddings (``UpsertChunkEmbedding``). A implementacao concreta hoje (V3) e'
``infrastructure/qdrant/qdrant_vector_repository.py``, escolhida por
``factories/embeddings_factory.py``.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.embeddings.application.dto import (
    ChunkEmbeddingRecord,
    ChunkSearchResult,
)


class VectorRepository(ABC):
    """Persiste e busca vetores de chunks."""

    @abstractmethod
    async def upsert(self, record: ChunkEmbeddingRecord) -> None:
        """Insere ou atualiza o vetor de um chunk."""

    @abstractmethod
    async def search(
        self,
        query_vector: tuple[float, ...],
        *,
        limit: int = 5,
        source_type: str | None = None,
        document_ids: list[UUID] | None = None,
    ) -> list[ChunkSearchResult]:
        """Busca os chunks mais proximos do vetor de consulta informado."""

    @abstractmethod
    async def get_by_chunk_id(self, chunk_id: UUID) -> ChunkEmbeddingRecord | None:
        """Recupera o vetor ja armazenado para um chunk_id, se existir.

        Usado para reaproveitar um vetor existente (cache por content_hash)
        sem chamar o provider de embedding de novo.
        """

    @abstractmethod
    async def delete_by_document_id(self, document_id: UUID) -> None:
        """Remove todos os vetores de chunks de um documento.

        Usado por `orchestration` para limpar vetores orfaos quando uma URL
        e' re-raspada e gera um `Document` novo - o antigo nao e' mais "a
        versao atual" daquela URL. Nao-op se nao houver vetor (idempotente).
        """
