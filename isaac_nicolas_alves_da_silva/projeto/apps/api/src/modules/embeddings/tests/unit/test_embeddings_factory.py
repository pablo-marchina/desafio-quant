"""Testes da composicao de dependencias do modulo embeddings."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.api.src.modules.embeddings.application.dto import GenerateChunkEmbeddingInput
from apps.api.src.modules.embeddings.application.use_cases.create_embedding_job import (
    CreateEmbeddingJob,
)
from apps.api.src.modules.embeddings.application.use_cases.execute_embedding_job import (
    ExecuteEmbeddingJob,
)
from apps.api.src.modules.embeddings.application.use_cases.generate_chunk_embedding import (
    GenerateChunkEmbedding,
)
from apps.api.src.modules.embeddings.application.use_cases.get_embedding_job import (
    GetEmbeddingJob,
)
from apps.api.src.modules.embeddings.application.use_cases.upsert_chunk_embedding import (
    UpsertChunkEmbedding,
)
from apps.api.src.modules.embeddings.domain.exceptions import (
    EmbeddingServiceUnavailableError,
)
from apps.api.src.modules.embeddings.factories import embeddings_factory as factory_module
from apps.api.src.modules.embeddings.factories.embeddings_factory import EmbeddingsFactory
from apps.api.src.modules.embeddings.infrastructure.gemini.gemini_embedding_provider import (
    GeminiEmbeddingProvider,
)
from apps.api.src.modules.embeddings.infrastructure.ingestion_adapters.ingestion_chunk_reader import (
    IngestionChunkReader,
)
from apps.api.src.modules.embeddings.infrastructure.qdrant.qdrant_vector_repository import (
    QdrantVectorRepository,
)


def _fake_settings(*, gemini_api_key: str) -> SimpleNamespace:
    return SimpleNamespace(
        gemini_api_key=gemini_api_key,
        gemini_embedding_model="models/embedding-test",
    )


def test_create_embedding_service_returns_none_without_gemini_api_key(monkeypatch) -> None:
    monkeypatch.setattr(
        factory_module, "get_settings", lambda: _fake_settings(gemini_api_key="")
    )

    assert EmbeddingsFactory.create_embedding_service() is None


def test_create_embedding_service_returns_gemini_provider_when_api_key_present(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        factory_module, "get_settings", lambda: _fake_settings(gemini_api_key="secret")
    )

    service = EmbeddingsFactory.create_embedding_service()

    assert isinstance(service, GeminiEmbeddingProvider)


def test_create_generate_chunk_embedding_returns_use_case() -> None:
    use_case = EmbeddingsFactory.create_generate_chunk_embedding()

    assert isinstance(use_case, GenerateChunkEmbedding)


@pytest.mark.anyio
async def test_create_generate_chunk_embedding_raises_without_gemini_api_key(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        factory_module, "get_settings", lambda: _fake_settings(gemini_api_key="")
    )
    use_case = EmbeddingsFactory.create_generate_chunk_embedding()

    with pytest.raises(EmbeddingServiceUnavailableError):
        await use_case.execute(
            GenerateChunkEmbeddingInput(chunk_id=uuid4(), text="texto valido")
        )


def test_create_vector_repository_returns_qdrant_repository() -> None:
    repository = EmbeddingsFactory.create_vector_repository()

    assert isinstance(repository, QdrantVectorRepository)


def test_create_upsert_chunk_embedding_returns_use_case() -> None:
    use_case = EmbeddingsFactory.create_upsert_chunk_embedding()

    assert isinstance(use_case, UpsertChunkEmbedding)


def test_create_chunk_source_reader_returns_ingestion_chunk_reader() -> None:
    reader = EmbeddingsFactory.create_chunk_source_reader()

    assert isinstance(reader, IngestionChunkReader)


def test_create_create_embedding_job_returns_use_case() -> None:
    use_case = EmbeddingsFactory.create_create_embedding_job()

    assert isinstance(use_case, CreateEmbeddingJob)


def test_create_execute_embedding_job_returns_use_case() -> None:
    use_case = EmbeddingsFactory.create_execute_embedding_job()

    assert isinstance(use_case, ExecuteEmbeddingJob)


def test_create_get_embedding_job_returns_use_case() -> None:
    use_case = EmbeddingsFactory.create_get_embedding_job()

    assert isinstance(use_case, GetEmbeddingJob)
