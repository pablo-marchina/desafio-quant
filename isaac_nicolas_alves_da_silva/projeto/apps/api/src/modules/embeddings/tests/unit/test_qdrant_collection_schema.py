"""Testes do schema de modelo/dimensao da colecao Qdrant."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from apps.api.src.modules.embeddings.domain.exceptions import (
    EmbeddingCollectionSchemaMismatchError,
)
from apps.api.src.modules.embeddings.infrastructure.qdrant.qdrant_vector_repository import (
    QdrantVectorRepository,
)


def _collection(*, dimension: int, model_name: str | None):
    return SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(vectors=SimpleNamespace(size=dimension)),
            metadata=(
                {"embedding_dimension": dimension, "embedding_model_name": model_name}
                if model_name is not None
                else {}
            ),
        )
    )


@pytest.mark.anyio
async def test_creates_collection_with_embedding_schema_metadata() -> None:
    repository = QdrantVectorRepository(url="http://unused", collection_name="chunks")
    repository._client = AsyncMock()
    repository._client.collection_exists.return_value = False

    await repository._ensure_collection(3, "models/gemini-embedding-001")

    create_kwargs = repository._client.create_collection.await_args.kwargs
    assert create_kwargs["vectors_config"].size == 3
    assert create_kwargs["metadata"] == {
        "embedding_dimension": 3,
        "embedding_model_name": "models/gemini-embedding-001",
    }


@pytest.mark.anyio
async def test_rejects_embedding_model_change_for_existing_collection() -> None:
    repository = QdrantVectorRepository(url="http://unused", collection_name="chunks")
    repository._client = AsyncMock()
    repository._client.collection_exists.return_value = True
    repository._client.get_collection.return_value = _collection(
        dimension=3, model_name="models/gemini-embedding-001"
    )

    with pytest.raises(EmbeddingCollectionSchemaMismatchError, match="modelo"):
        await repository._ensure_collection(3, "models/other-embedding")


@pytest.mark.anyio
async def test_rejects_embedding_dimension_change_for_existing_collection() -> None:
    repository = QdrantVectorRepository(url="http://unused", collection_name="chunks")
    repository._client = AsyncMock()
    repository._client.collection_exists.return_value = True
    repository._client.get_collection.return_value = _collection(
        dimension=3, model_name="models/gemini-embedding-001"
    )

    with pytest.raises(EmbeddingCollectionSchemaMismatchError, match="dimensao"):
        await repository._ensure_collection(4, "models/gemini-embedding-001")
