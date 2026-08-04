"""Testes do caso de uso CreateEmbeddingJob."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.embeddings.application.dto import CreateEmbeddingJobInput
from apps.api.src.modules.embeddings.application.ports import EmbeddingTaskDispatcher
from apps.api.src.modules.embeddings.application.unit_of_work import (
    EmbeddingsUnitOfWork,
)
from apps.api.src.modules.embeddings.application.use_cases.create_embedding_job import (
    CreateEmbeddingJob,
)
from apps.api.src.modules.embeddings.domain.entities import EmbeddingJob, EmbeddingJobChunk
from apps.api.src.modules.embeddings.domain.enums import EmbeddingJobStatus
from apps.api.src.modules.embeddings.domain.exceptions import EmbeddingTaskDispatchError
from apps.api.src.modules.embeddings.domain.repositories import (
    EmbeddingJobChunkRepository,
    EmbeddingJobRepository,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeJobRepo(EmbeddingJobRepository):
    def __init__(self) -> None:
        self._jobs: dict[UUID, EmbeddingJob] = {}

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
    def __init__(self, job_repo: FakeJobRepo) -> None:
        self.job_repository = job_repo
        self.job_chunk_repository = FakeJobChunkRepo()
        self.committed = False

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
        self.committed = True

    async def rollback(self) -> None:
        pass


class FakeDispatcher(EmbeddingTaskDispatcher):
    def __init__(self, should_fail: bool = False) -> None:
        self._should_fail = should_fail
        self.dispatched: list[UUID] = []

    async def dispatch(self, *, job_id: UUID) -> None:
        if self._should_fail:
            raise EmbeddingTaskDispatchError("redis fora do ar")
        self.dispatched.append(job_id)


def _make_use_case(
    should_fail_dispatch: bool = False,
) -> tuple[CreateEmbeddingJob, FakeJobRepo, FakeDispatcher]:
    job_repo = FakeJobRepo()
    dispatcher = FakeDispatcher(should_fail=should_fail_dispatch)
    uow = FakeUoW(job_repo)
    use_case = CreateEmbeddingJob(
        uow_factory=lambda: uow,
        task_dispatcher=dispatcher,
    )
    return use_case, job_repo, dispatcher


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_creates_job_with_pending_status() -> None:
    use_case, job_repo, _ = _make_use_case()
    document_id = uuid4()

    view = await use_case.execute(CreateEmbeddingJobInput(document_id=document_id))

    saved = await job_repo.get_by_id(view.id)
    assert saved is not None
    assert saved.status is EmbeddingJobStatus.PENDING
    assert saved.document_id == document_id


@pytest.mark.anyio
async def test_dispatches_job_id_to_queue() -> None:
    use_case, _, dispatcher = _make_use_case()

    view = await use_case.execute(CreateEmbeddingJobInput(document_id=uuid4()))

    assert view.id in dispatcher.dispatched


@pytest.mark.anyio
async def test_fails_job_when_dispatch_fails() -> None:
    use_case, job_repo, _ = _make_use_case(should_fail_dispatch=True)

    with pytest.raises(EmbeddingTaskDispatchError):
        await use_case.execute(CreateEmbeddingJobInput(document_id=uuid4()))

    all_jobs = list(job_repo._jobs.values())
    assert len(all_jobs) == 1
    assert all_jobs[0].status is EmbeddingJobStatus.FAILED
