"""Testes do caso de uso GetEmbeddingJob."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.embeddings.application.unit_of_work import (
    EmbeddingsUnitOfWork,
)
from apps.api.src.modules.embeddings.application.use_cases.get_embedding_job import (
    GetEmbeddingJob,
)
from apps.api.src.modules.embeddings.domain.entities import EmbeddingJob, EmbeddingJobChunk
from apps.api.src.modules.embeddings.domain.exceptions import EmbeddingJobNotFoundError
from apps.api.src.modules.embeddings.domain.repositories import (
    EmbeddingJobChunkRepository,
    EmbeddingJobRepository,
)


class FakeJobRepo(EmbeddingJobRepository):
    def __init__(self, jobs: dict[UUID, EmbeddingJob]) -> None:
        self._jobs = jobs

    async def save(self, job: EmbeddingJob) -> None:
        self._jobs[job.id] = job

    async def get_by_id(self, job_id: UUID) -> EmbeddingJob | None:
        return self._jobs.get(job_id)


class FakeJobChunkRepo(EmbeddingJobChunkRepository):
    async def save(self, chunk: EmbeddingJobChunk) -> None:
        pass

    async def list_by_job_id(self, job_id: UUID) -> list[EmbeddingJobChunk]:
        return []

    async def find_completed_by_content_hash(
        self, content_hash: str, *, model_name: str
    ) -> EmbeddingJobChunk | None:
        return None


class FakeUoW(EmbeddingsUnitOfWork):
    def __init__(self, jobs: dict[UUID, EmbeddingJob]) -> None:
        self.job_repository = FakeJobRepo(jobs)
        self.job_chunk_repository = FakeJobChunkRepo()

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


@pytest.mark.anyio
async def test_returns_view_for_existing_job() -> None:
    job = EmbeddingJob(document_id=uuid4())
    jobs = {job.id: job}
    use_case = GetEmbeddingJob(lambda: FakeUoW(jobs))

    view = await use_case.execute(job_id=job.id)

    assert view.id == job.id
    assert view.document_id == job.document_id


@pytest.mark.anyio
async def test_raises_when_job_not_found() -> None:
    use_case = GetEmbeddingJob(lambda: FakeUoW({}))

    with pytest.raises(EmbeddingJobNotFoundError):
        await use_case.execute(job_id=uuid4())
