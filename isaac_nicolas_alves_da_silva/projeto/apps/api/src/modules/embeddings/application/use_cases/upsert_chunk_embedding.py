"""Caso de uso para gerar e persistir o embedding de um chunk."""

from uuid import UUID

from apps.api.src.modules.embeddings.application.dto import (
    ChunkEmbeddingRecord,
    ChunkEmbeddingView,
    GenerateChunkEmbeddingInput,
    UpsertChunkEmbeddingInput,
)
from apps.api.src.modules.embeddings.application.public.vector_repository import (
    VectorRepository,
)
from apps.api.src.modules.embeddings.application.use_cases.generate_chunk_embedding import (
    GenerateChunkEmbedding,
)


class UpsertChunkEmbedding:
    """Gera o embedding de um chunk e o persiste no VectorRepository.

    Quando ``cached_chunk_id`` e informado e ja existe vetor salvo para ele
    (mesmo content_hash + modelo, verificado pelo chamador), reusa esse
    vetor em vez de chamar o provider de embedding de novo.
    """

    def __init__(
        self,
        *,
        generate_chunk_embedding: GenerateChunkEmbedding,
        vector_repository: VectorRepository,
    ) -> None:
        self._generate_chunk_embedding = generate_chunk_embedding
        self._vector_repository = vector_repository

    async def execute(
        self,
        upsert_input: UpsertChunkEmbeddingInput,
        *,
        cached_chunk_id: UUID | None = None,
    ) -> ChunkEmbeddingView:
        cached = (
            await self._vector_repository.get_by_chunk_id(cached_chunk_id)
            if cached_chunk_id is not None
            else None
        )

        if cached is not None:
            view = ChunkEmbeddingView(
                chunk_id=upsert_input.chunk_id,
                values=cached.values,
                dimension=cached.dimension,
                model_name=cached.model_name,
            )
        else:
            view = await self._generate_chunk_embedding.execute(
                GenerateChunkEmbeddingInput(
                    chunk_id=upsert_input.chunk_id, text=upsert_input.text
                )
            )

        await self._vector_repository.upsert(
            ChunkEmbeddingRecord(
                chunk_id=view.chunk_id,
                document_id=upsert_input.document_id,
                source_url=upsert_input.source_url,
                source_type=upsert_input.source_type,
                values=view.values,
                dimension=view.dimension,
                model_name=view.model_name,
            )
        )
        return view
