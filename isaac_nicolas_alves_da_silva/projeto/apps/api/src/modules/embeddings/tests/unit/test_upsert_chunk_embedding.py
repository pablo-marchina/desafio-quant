"""Testes do caso de uso UpsertChunkEmbedding."""

from uuid import uuid4

import pytest

from apps.api.src.modules.embeddings.application.dto import (
    ChunkEmbeddingRecord,
    ChunkEmbeddingView,
    ChunkSearchResult,
    GenerateChunkEmbeddingInput,
    UpsertChunkEmbeddingInput,
)
from apps.api.src.modules.embeddings.application.public.embedding_service import (
    EmbeddingService,
)
from apps.api.src.modules.embeddings.application.public.vector_repository import (
    VectorRepository,
)
from apps.api.src.modules.embeddings.application.use_cases.generate_chunk_embedding import (
    GenerateChunkEmbedding,
)
from apps.api.src.modules.embeddings.application.use_cases.upsert_chunk_embedding import (
    UpsertChunkEmbedding,
)
from apps.api.src.modules.embeddings.infrastructure.fake.deterministic_fake_provider import (
    DeterministicFakeEmbeddingProvider,
)


class FakeVectorRepository(VectorRepository):
    def __init__(self) -> None:
        self.records: dict = {}

    async def upsert(self, record: ChunkEmbeddingRecord) -> None:
        self.records[record.chunk_id] = record

    async def search(
        self,
        query_vector: tuple[float, ...],
        *,
        limit: int = 5,
        source_type: str | None = None,
        document_ids=None,
    ) -> list[ChunkSearchResult]:
        return []

    async def get_by_chunk_id(self, chunk_id) -> ChunkEmbeddingRecord | None:
        return self.records.get(chunk_id)

    async def delete_by_document_id(self, document_id) -> None:
        self.records = {
            chunk_id: record
            for chunk_id, record in self.records.items()
            if record.document_id != document_id
        }


class CountingEmbeddingService(EmbeddingService):
    def __init__(self) -> None:
        self.call_count = 0

    async def embed(
        self, embedding_input: GenerateChunkEmbeddingInput
    ) -> ChunkEmbeddingView:
        self.call_count += 1
        return ChunkEmbeddingView(
            chunk_id=embedding_input.chunk_id,
            values=(0.5, 0.6),
            dimension=2,
            model_name="fake-counting",
        )


@pytest.mark.anyio
async def test_execute_generates_and_persists_embedding() -> None:
    vector_repository = FakeVectorRepository()
    use_case = UpsertChunkEmbedding(
        generate_chunk_embedding=GenerateChunkEmbedding(
            embedding_service=DeterministicFakeEmbeddingProvider()
        ),
        vector_repository=vector_repository,
    )
    chunk_id = uuid4()
    document_id = uuid4()

    await use_case.execute(
        UpsertChunkEmbeddingInput(
            chunk_id=chunk_id,
            document_id=document_id,
            source_url="https://startup.example.com",
            source_type="nvidia_knowledge",
            text="a NVIDIA recomenda NIM para servir LLMs",
        )
    )

    record = vector_repository.records[chunk_id]
    assert record.document_id == document_id
    assert record.source_url == "https://startup.example.com"
    assert record.source_type == "nvidia_knowledge"
    assert len(record.values) == record.dimension


@pytest.mark.anyio
async def test_execute_reuses_cached_vector_without_calling_embedding_service() -> None:
    vector_repository = FakeVectorRepository()
    embedding_service = CountingEmbeddingService()
    use_case = UpsertChunkEmbedding(
        generate_chunk_embedding=GenerateChunkEmbedding(
            embedding_service=embedding_service
        ),
        vector_repository=vector_repository,
    )
    cached_chunk_id = uuid4()
    await vector_repository.upsert(
        ChunkEmbeddingRecord(
            chunk_id=cached_chunk_id,
            document_id=uuid4(),
            source_url="https://other.example.com",
            source_type="nvidia_knowledge",
            values=(0.9, 0.8),
            dimension=2,
            model_name="fake-counting",
        )
    )

    new_chunk_id = uuid4()
    document_id = uuid4()
    view = await use_case.execute(
        UpsertChunkEmbeddingInput(
            chunk_id=new_chunk_id,
            document_id=document_id,
            source_url="https://startup.example.com",
            source_type="nvidia_knowledge",
            text="texto identico a um chunk ja embeddado antes",
        ),
        cached_chunk_id=cached_chunk_id,
    )

    assert embedding_service.call_count == 0
    assert view.values == (0.9, 0.8)
    new_record = vector_repository.records[new_chunk_id]
    assert new_record.document_id == document_id
    assert new_record.values == (0.9, 0.8)


@pytest.mark.anyio
async def test_execute_falls_back_to_generation_when_cache_miss() -> None:
    vector_repository = FakeVectorRepository()
    embedding_service = CountingEmbeddingService()
    use_case = UpsertChunkEmbedding(
        generate_chunk_embedding=GenerateChunkEmbedding(
            embedding_service=embedding_service
        ),
        vector_repository=vector_repository,
    )

    await use_case.execute(
        UpsertChunkEmbeddingInput(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source_url="https://startup.example.com",
            source_type="nvidia_knowledge",
            text="texto novo",
        ),
        cached_chunk_id=uuid4(),
    )

    assert embedding_service.call_count == 1
