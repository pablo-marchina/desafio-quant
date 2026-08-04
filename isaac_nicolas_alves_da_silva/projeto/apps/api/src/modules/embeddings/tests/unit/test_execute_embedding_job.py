"""Testes do caso de uso ExecuteEmbeddingJob."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.embeddings.application.dto import (
    ChunkEmbeddingRecord,
    ChunkEmbeddingView,
    ChunkSearchResult,
    ChunkSourceItem,
    GenerateChunkEmbeddingInput,
)
from apps.api.src.modules.embeddings.application.ports import ChunkSourceReader
from apps.api.src.modules.embeddings.application.public.embedding_service import (
    EmbeddingService,
)
from apps.api.src.modules.embeddings.application.public.vector_repository import (
    VectorRepository,
)
from apps.api.src.modules.embeddings.application.unit_of_work import (
    EmbeddingsUnitOfWork,
)
from apps.api.src.modules.embeddings.application.use_cases.execute_embedding_job import (
    ExecuteEmbeddingJob,
)
from apps.api.src.modules.embeddings.application.use_cases.generate_chunk_embedding import (
    GenerateChunkEmbedding,
)
from apps.api.src.modules.embeddings.application.use_cases.upsert_chunk_embedding import (
    UpsertChunkEmbedding,
)
from apps.api.src.modules.embeddings.domain.entities import (
    MAX_CHUNK_ATTEMPTS,
    EmbeddingJob,
    EmbeddingJobChunk,
)
from apps.api.src.modules.embeddings.domain.enums import (
    EmbeddingJobChunkStatus,
    EmbeddingJobStatus,
)
from apps.api.src.modules.embeddings.domain.exceptions import (
    EmbeddingGenerationError,
    EmbeddingJobNotFoundError,
    EmbeddingJobPartiallyFailedError,
)
from apps.api.src.modules.embeddings.domain.repositories import (
    EmbeddingJobChunkRepository,
    EmbeddingJobRepository,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class ControllableEmbeddingService(EmbeddingService):
    def __init__(self, *, fail_chunk_ids: set[UUID] | None = None) -> None:
        self._fail_chunk_ids = fail_chunk_ids or set()
        self.calls: list[UUID] = []

    async def embed(
        self, embedding_input: GenerateChunkEmbeddingInput
    ) -> ChunkEmbeddingView:
        self.calls.append(embedding_input.chunk_id)
        if embedding_input.chunk_id in self._fail_chunk_ids:
            raise EmbeddingGenerationError("falha simulada")
        return ChunkEmbeddingView(
            chunk_id=embedding_input.chunk_id,
            values=(0.1, 0.2),
            dimension=2,
            model_name="fake-test",
        )


class FakeVectorRepository(VectorRepository):
    def __init__(self) -> None:
        self.records: dict[UUID, ChunkEmbeddingRecord] = {}

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

    async def get_by_chunk_id(self, chunk_id: UUID) -> ChunkEmbeddingRecord | None:
        return self.records.get(chunk_id)

    async def delete_by_document_id(self, document_id: UUID) -> None:
        self.records = {
            chunk_id: record
            for chunk_id, record in self.records.items()
            if record.document_id != document_id
        }


class FakeChunkSourceReader(ChunkSourceReader):
    def __init__(self, chunks_by_document: dict[UUID, list[ChunkSourceItem]]) -> None:
        self._chunks_by_document = chunks_by_document
        self.calls: list[UUID] = []

    async def list_chunks(self, document_id: UUID) -> list[ChunkSourceItem]:
        self.calls.append(document_id)
        return self._chunks_by_document.get(document_id, [])


class FakeJobRepo(EmbeddingJobRepository):
    def __init__(self) -> None:
        self.jobs: dict[UUID, EmbeddingJob] = {}

    async def save(self, job: EmbeddingJob) -> None:
        self.jobs[job.id] = job

    async def get_by_id(self, job_id: UUID) -> EmbeddingJob | None:
        return self.jobs.get(job_id)


class FakeJobChunkRepo(EmbeddingJobChunkRepository):
    def __init__(self) -> None:
        self.chunks: dict[UUID, EmbeddingJobChunk] = {}

    async def save(self, chunk: EmbeddingJobChunk) -> None:
        self.chunks[chunk.id] = chunk

    async def list_by_job_id(self, job_id: UUID) -> list[EmbeddingJobChunk]:
        return [c for c in self.chunks.values() if c.job_id == job_id]

    async def find_completed_by_content_hash(
        self, content_hash: str, *, model_name: str
    ) -> EmbeddingJobChunk | None:
        for chunk in self.chunks.values():
            if (
                chunk.status is EmbeddingJobChunkStatus.COMPLETED
                and chunk.content_hash == content_hash
                and chunk.model_name == model_name
            ):
                return chunk
        return None


class FakeUoW(EmbeddingsUnitOfWork):
    def __init__(self, job_repo: FakeJobRepo, job_chunk_repo: FakeJobChunkRepo) -> None:
        self.job_repository = job_repo
        self.job_chunk_repository = job_chunk_repo

    async def __aenter__(self) -> "FakeUoW":
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


def _make_setup(
    *,
    chunk_items: list[ChunkSourceItem],
    fail_chunk_ids: set[UUID] | None = None,
):
    document_id = uuid4()
    job = EmbeddingJob(document_id=document_id)

    job_repo = FakeJobRepo()
    job_repo.jobs[job.id] = job
    job_chunk_repo = FakeJobChunkRepo()
    uow = FakeUoW(job_repo, job_chunk_repo)

    chunk_source_reader = FakeChunkSourceReader({document_id: chunk_items})
    embedding_service = ControllableEmbeddingService(fail_chunk_ids=fail_chunk_ids)
    vector_repository = FakeVectorRepository()
    upsert_chunk_embedding = UpsertChunkEmbedding(
        generate_chunk_embedding=GenerateChunkEmbedding(
            embedding_service=embedding_service
        ),
        vector_repository=vector_repository,
    )

    use_case = ExecuteEmbeddingJob(
        uow_factory=lambda: uow,
        chunk_source_reader=chunk_source_reader,
        upsert_chunk_embedding=upsert_chunk_embedding,
        current_model_name="fake-test",
    )

    return use_case, job, job_repo, job_chunk_repo, embedding_service, vector_repository


def _make_chunks(n: int) -> list[ChunkSourceItem]:
    return [
        ChunkSourceItem(chunk_id=uuid4(), text=f"texto {i}", source_url="https://x.example.com")
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_all_chunks_succeed_marks_job_completed() -> None:
    chunks = _make_chunks(3)
    use_case, job, job_repo, job_chunk_repo, _, vector_repository = _make_setup(
        chunk_items=chunks
    )

    await use_case.execute(job_id=job.id)

    assert job_repo.jobs[job.id].status is EmbeddingJobStatus.COMPLETED
    assert job_repo.jobs[job.id].succeeded_chunks == 3
    assert job_repo.jobs[job.id].failed_chunks == 0
    assert job_repo.jobs[job.id].total_input_char_count == sum(
        len(chunk.text) for chunk in chunks
    )
    assert job_repo.jobs[job.id].total_estimated_input_tokens == 6
    rows = job_chunk_repo.chunks.values()
    assert all(row.status is EmbeddingJobChunkStatus.COMPLETED for row in rows)
    assert all(row.model_name == "fake-test" for row in rows)
    assert all(row.vector_dimension == 2 for row in rows)
    assert all(row.content_hash is not None for row in rows)
    assert len(vector_repository.records) == 3


@pytest.mark.anyio
async def test_partial_failure_below_threshold_raises_for_retry() -> None:
    chunks = _make_chunks(3)
    failing_id = chunks[1].chunk_id
    use_case, job, job_repo, job_chunk_repo, _, _ = _make_setup(
        chunk_items=chunks, fail_chunk_ids={failing_id}
    )

    with pytest.raises(EmbeddingJobPartiallyFailedError):
        await use_case.execute(job_id=job.id)

    assert job_repo.jobs[job.id].status is EmbeddingJobStatus.RUNNING
    rows = {c.chunk_id: c for c in job_chunk_repo.chunks.values()}
    assert rows[failing_id].status is EmbeddingJobChunkStatus.PENDING
    assert rows[failing_id].attempt_count == 1
    others = [row for cid, row in rows.items() if cid != failing_id]
    assert all(row.status is EmbeddingJobChunkStatus.COMPLETED for row in others)


@pytest.mark.anyio
async def test_chunk_failing_repeatedly_becomes_terminal_and_job_partial() -> None:
    chunks = _make_chunks(3)
    failing_id = chunks[1].chunk_id
    use_case, job, job_repo, job_chunk_repo, embedding_service, _ = _make_setup(
        chunk_items=chunks, fail_chunk_ids={failing_id}
    )

    for _ in range(MAX_CHUNK_ATTEMPTS - 1):
        with pytest.raises(EmbeddingJobPartiallyFailedError):
            await use_case.execute(job_id=job.id)

    await use_case.execute(job_id=job.id)  # ultima tentativa: nao deve levantar

    assert job_repo.jobs[job.id].status is EmbeddingJobStatus.PARTIAL
    rows = {c.chunk_id: c for c in job_chunk_repo.chunks.values()}
    assert rows[failing_id].status is EmbeddingJobChunkStatus.FAILED
    assert rows[failing_id].attempt_count == MAX_CHUNK_ATTEMPTS
    # so reprocessou o chunk que falhou, nunca os ja completados
    assert embedding_service.calls.count(failing_id) == MAX_CHUNK_ATTEMPTS
    for chunk in chunks:
        if chunk.chunk_id != failing_id:
            assert embedding_service.calls.count(chunk.chunk_id) == 1


@pytest.mark.anyio
async def test_all_chunks_fail_eventually_marks_job_failed() -> None:
    chunks = _make_chunks(2)
    all_ids = {c.chunk_id for c in chunks}
    use_case, job, job_repo, _, _, _ = _make_setup(
        chunk_items=chunks, fail_chunk_ids=all_ids
    )

    for _ in range(MAX_CHUNK_ATTEMPTS - 1):
        with pytest.raises(EmbeddingJobPartiallyFailedError):
            await use_case.execute(job_id=job.id)

    await use_case.execute(job_id=job.id)

    assert job_repo.jobs[job.id].status is EmbeddingJobStatus.FAILED
    assert job_repo.jobs[job.id].error_message is not None
    assert "2 chunk(s) falharam" in job_repo.jobs[job.id].error_message
    assert "EmbeddingGenerationError: falha simulada" in job_repo.jobs[job.id].error_message


@pytest.mark.anyio
async def test_document_with_no_chunks_fails_job_immediately() -> None:
    use_case, job, job_repo, _, chunk_source_reader, _ = _make_setup(chunk_items=[])

    await use_case.execute(job_id=job.id)

    assert job_repo.jobs[job.id].status is EmbeddingJobStatus.FAILED
    assert job_repo.jobs[job.id].error_message is not None


@pytest.mark.anyio
async def test_already_finished_job_is_noop() -> None:
    chunks = _make_chunks(1)
    use_case, job, job_repo, _, embedding_service, _ = _make_setup(chunk_items=chunks)
    job.start(total_chunks=1)
    job.finish(succeeded=1, failed=0)
    job_repo.jobs[job.id] = job

    await use_case.execute(job_id=job.id)

    assert embedding_service.calls == []


@pytest.mark.anyio
async def test_raises_when_job_not_found() -> None:
    use_case, _, _, _, _, _ = _make_setup(chunk_items=[])

    with pytest.raises(EmbeddingJobNotFoundError):
        await use_case.execute(job_id=uuid4())


@pytest.mark.anyio
async def test_chunk_with_identical_text_across_documents_reuses_vector() -> None:
    """Boilerplate repetido entre paginas diferentes nao deve chamar o
    provider de embedding de novo - so o primeiro chunk gera vetor."""

    shared_text = "paragrafo de boilerplate identico entre paginas"
    document_a, document_b = uuid4(), uuid4()
    chunk_a = ChunkSourceItem(
        chunk_id=uuid4(), text=shared_text, source_url="https://a.example.com"
    )
    chunk_b = ChunkSourceItem(
        chunk_id=uuid4(), text=shared_text, source_url="https://b.example.com"
    )

    job_a = EmbeddingJob(document_id=document_a)
    job_b = EmbeddingJob(document_id=document_b)
    job_repo = FakeJobRepo()
    job_repo.jobs[job_a.id] = job_a
    job_repo.jobs[job_b.id] = job_b
    job_chunk_repo = FakeJobChunkRepo()
    uow = FakeUoW(job_repo, job_chunk_repo)

    chunk_source_reader = FakeChunkSourceReader(
        {document_a: [chunk_a], document_b: [chunk_b]}
    )
    embedding_service = ControllableEmbeddingService()
    vector_repository = FakeVectorRepository()
    upsert_chunk_embedding = UpsertChunkEmbedding(
        generate_chunk_embedding=GenerateChunkEmbedding(
            embedding_service=embedding_service
        ),
        vector_repository=vector_repository,
    )
    use_case = ExecuteEmbeddingJob(
        uow_factory=lambda: uow,
        chunk_source_reader=chunk_source_reader,
        upsert_chunk_embedding=upsert_chunk_embedding,
        current_model_name="fake-test",
    )

    await use_case.execute(job_id=job_a.id)
    await use_case.execute(job_id=job_b.id)

    assert embedding_service.calls == [chunk_a.chunk_id]
    assert (
        vector_repository.records[chunk_a.chunk_id].values
        == vector_repository.records[chunk_b.chunk_id].values
    )
    assert job_repo.jobs[job_b.id].status is EmbeddingJobStatus.COMPLETED
