"""Testes do provider real de embeddings via Gemini."""

from uuid import uuid4

import pytest

from apps.api.src.modules.embeddings.application.dto import GenerateChunkEmbeddingInput
from apps.api.src.modules.embeddings.domain.exceptions import EmbeddingGenerationError
from apps.api.src.modules.embeddings.infrastructure.gemini.gemini_embedding_provider import (
    GeminiEmbeddingProvider,
)


class FakeEmbeddingClient:
    def __init__(self, *, values: list[float] | None = None, error: Exception | None = None) -> None:
        self._values = values
        self._error = error
        self.calls: list[str] = []

    async def aembed_query(self, text: str) -> list[float]:
        self.calls.append(text)
        if self._error is not None:
            raise self._error
        return self._values or [0.1, 0.2, 0.3]


def test_requires_api_key() -> None:
    with pytest.raises(ValueError):
        GeminiEmbeddingProvider(api_key="", model="models/embedding-test")


def test_requires_model() -> None:
    with pytest.raises(ValueError):
        GeminiEmbeddingProvider(api_key="secret", model="")


@pytest.mark.anyio
async def test_embed_maps_client_result_to_view() -> None:
    client = FakeEmbeddingClient(values=[0.1, 0.2, 0.3, 0.4])
    provider = GeminiEmbeddingProvider(
        api_key="secret", model="models/embedding-test", embedding_client=client
    )
    chunk_id = uuid4()

    view = await provider.embed(
        GenerateChunkEmbeddingInput(chunk_id=chunk_id, text="texto do chunk")
    )

    assert view.chunk_id == chunk_id
    assert view.values == (0.1, 0.2, 0.3, 0.4)
    assert view.dimension == 4
    assert view.model_name == "models/embedding-test"
    assert client.calls == ["texto do chunk"]


@pytest.mark.anyio
async def test_embed_wraps_client_error() -> None:
    client = FakeEmbeddingClient(error=RuntimeError("api fora do ar"))
    provider = GeminiEmbeddingProvider(
        api_key="secret", model="models/embedding-test", embedding_client=client
    )

    with pytest.raises(EmbeddingGenerationError):
        await provider.embed(
            GenerateChunkEmbeddingInput(chunk_id=uuid4(), text="texto do chunk")
        )
