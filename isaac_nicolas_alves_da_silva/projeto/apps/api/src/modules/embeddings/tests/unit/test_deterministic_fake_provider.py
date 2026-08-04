"""Testes do provider fake deterministico de embeddings."""

from uuid import uuid4

import pytest

from apps.api.src.modules.embeddings.application.dto import GenerateChunkEmbeddingInput
from apps.api.src.modules.embeddings.infrastructure.fake.deterministic_fake_provider import (
    DEFAULT_DIMENSION,
    MODEL_NAME,
    DeterministicFakeEmbeddingProvider,
)


@pytest.mark.anyio
async def test_same_text_produces_same_vector() -> None:
    provider = DeterministicFakeEmbeddingProvider()
    text = "a NVIDIA recomenda Triton para inferencia em escala"

    first = await provider.embed(GenerateChunkEmbeddingInput(chunk_id=uuid4(), text=text))
    second = await provider.embed(GenerateChunkEmbeddingInput(chunk_id=uuid4(), text=text))

    assert first.values == second.values


@pytest.mark.anyio
async def test_different_text_produces_different_vector() -> None:
    provider = DeterministicFakeEmbeddingProvider()

    first = await provider.embed(
        GenerateChunkEmbeddingInput(chunk_id=uuid4(), text="texto a")
    )
    second = await provider.embed(
        GenerateChunkEmbeddingInput(chunk_id=uuid4(), text="texto b")
    )

    assert first.values != second.values


@pytest.mark.anyio
async def test_vector_has_default_dimension() -> None:
    provider = DeterministicFakeEmbeddingProvider()

    result = await provider.embed(
        GenerateChunkEmbeddingInput(chunk_id=uuid4(), text="qualquer texto")
    )

    assert result.dimension == DEFAULT_DIMENSION
    assert len(result.values) == DEFAULT_DIMENSION


@pytest.mark.anyio
async def test_custom_dimension_is_respected() -> None:
    provider = DeterministicFakeEmbeddingProvider(dimension=32)

    result = await provider.embed(
        GenerateChunkEmbeddingInput(chunk_id=uuid4(), text="qualquer texto")
    )

    assert result.dimension == 32
    assert len(result.values) == 32


@pytest.mark.anyio
async def test_values_are_within_expected_range() -> None:
    provider = DeterministicFakeEmbeddingProvider()

    result = await provider.embed(
        GenerateChunkEmbeddingInput(chunk_id=uuid4(), text="qualquer texto")
    )

    assert all(-1.0 <= value <= 1.0 for value in result.values)


@pytest.mark.anyio
async def test_model_name_is_stable() -> None:
    provider = DeterministicFakeEmbeddingProvider()

    result = await provider.embed(
        GenerateChunkEmbeddingInput(chunk_id=uuid4(), text="qualquer texto")
    )

    assert result.model_name == MODEL_NAME == "fake-deterministic-v1"


@pytest.mark.anyio
async def test_chunk_id_is_preserved_in_result() -> None:
    provider = DeterministicFakeEmbeddingProvider()
    chunk_id = uuid4()

    result = await provider.embed(
        GenerateChunkEmbeddingInput(chunk_id=chunk_id, text="qualquer texto")
    )

    assert result.chunk_id == chunk_id
