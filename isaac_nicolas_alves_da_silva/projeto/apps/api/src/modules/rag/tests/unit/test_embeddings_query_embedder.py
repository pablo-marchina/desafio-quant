"""Testes do adapter EmbeddingsQueryEmbedder."""

import pytest

from apps.api.src.modules.embeddings.application.dto import (
    ChunkEmbeddingView,
    GenerateChunkEmbeddingInput,
)
from apps.api.src.modules.embeddings.application.public.embedding_service import (
    EmbeddingService,
)
from apps.api.src.modules.rag.domain.exceptions import RagSearchServiceUnavailableError
from apps.api.src.modules.rag.infrastructure.embeddings_adapters.embeddings_query_embedder import (
    EmbeddingsQueryEmbedder,
)


class FakeEmbeddingService(EmbeddingService):
    def __init__(self) -> None:
        self.received_inputs: list[GenerateChunkEmbeddingInput] = []

    async def embed(
        self, embedding_input: GenerateChunkEmbeddingInput
    ) -> ChunkEmbeddingView:
        self.received_inputs.append(embedding_input)
        return ChunkEmbeddingView(
            chunk_id=embedding_input.chunk_id,
            values=(0.1, 0.2, 0.3),
            dimension=3,
            model_name="fake-rag",
        )


@pytest.mark.anyio
async def test_generate_returns_vector_from_embedding_service() -> None:
    embedding_service = FakeEmbeddingService()
    embedder = EmbeddingsQueryEmbedder(embedding_service)

    vector = await embedder.generate("Como a startup usa IA?")

    assert vector == (0.1, 0.2, 0.3)
    assert embedding_service.received_inputs[0].text == "Como a startup usa IA?"


@pytest.mark.anyio
async def test_generate_raises_when_embedding_service_unavailable() -> None:
    embedder = EmbeddingsQueryEmbedder(None)

    with pytest.raises(RagSearchServiceUnavailableError):
        await embedder.generate("pergunta")
