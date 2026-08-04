"""Testes do caso de uso GenerateChunkEmbedding."""

from uuid import uuid4

import pytest

from apps.api.src.modules.embeddings.application.dto import (
    ChunkEmbeddingView,
    GenerateChunkEmbeddingInput,
)
from apps.api.src.modules.embeddings.application.public.embedding_service import (
    EmbeddingService,
)
from apps.api.src.modules.embeddings.application.use_cases.generate_chunk_embedding import (
    GenerateChunkEmbedding,
)
from apps.api.src.modules.embeddings.domain.exceptions import (
    EmbeddingServiceUnavailableError,
    EmptyChunkTextError,
)
from apps.api.src.modules.embeddings.infrastructure.fake.deterministic_fake_provider import (
    DeterministicFakeEmbeddingProvider,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeEmbeddingService(EmbeddingService):
    def __init__(self) -> None:
        self.calls: list[GenerateChunkEmbeddingInput] = []

    async def embed(
        self, embedding_input: GenerateChunkEmbeddingInput
    ) -> ChunkEmbeddingView:
        self.calls.append(embedding_input)
        return ChunkEmbeddingView(
            chunk_id=embedding_input.chunk_id,
            values=(0.1, 0.2, 0.3),
            dimension=3,
            model_name="fake-test",
        )


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_returns_embedding_for_chunk() -> None:
    service = FakeEmbeddingService()
    use_case = GenerateChunkEmbedding(embedding_service=service)
    chunk_id = uuid4()

    view = await use_case.execute(
        GenerateChunkEmbeddingInput(chunk_id=chunk_id, text="texto valido")
    )

    assert view.chunk_id == chunk_id
    assert view.dimension == 3


@pytest.mark.anyio
async def test_delegates_to_injected_embedding_service() -> None:
    service = FakeEmbeddingService()
    use_case = GenerateChunkEmbedding(embedding_service=service)
    embedding_input = GenerateChunkEmbeddingInput(chunk_id=uuid4(), text="texto valido")

    await use_case.execute(embedding_input)

    assert service.calls == [embedding_input]


@pytest.mark.anyio
async def test_raises_on_empty_text() -> None:
    service = FakeEmbeddingService()
    use_case = GenerateChunkEmbedding(embedding_service=service)

    with pytest.raises(EmptyChunkTextError):
        await use_case.execute(GenerateChunkEmbeddingInput(chunk_id=uuid4(), text="   "))

    assert service.calls == []


@pytest.mark.anyio
async def test_same_input_is_stable_across_executions() -> None:
    use_case = GenerateChunkEmbedding(embedding_service=DeterministicFakeEmbeddingProvider())
    embedding_input = GenerateChunkEmbeddingInput(
        chunk_id=uuid4(), text="a NVIDIA recomenda NIM para servir LLMs"
    )

    first = await use_case.execute(embedding_input)
    second = await use_case.execute(embedding_input)

    assert first.values == second.values


@pytest.mark.anyio
async def test_raises_when_no_embedding_service_configured() -> None:
    use_case = GenerateChunkEmbedding(embedding_service=None)

    with pytest.raises(EmbeddingServiceUnavailableError):
        await use_case.execute(
            GenerateChunkEmbeddingInput(chunk_id=uuid4(), text="texto valido")
        )
