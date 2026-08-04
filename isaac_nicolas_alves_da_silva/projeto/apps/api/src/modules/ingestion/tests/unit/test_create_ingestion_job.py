"""Testes do caso de uso CreateIngestionJob."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.ingestion.application.dto import CreateIngestionJobInput
from apps.api.src.modules.ingestion.application.ports import IngestionTaskDispatcher
from apps.api.src.modules.ingestion.application.unit_of_work import IngestionUnitOfWork
from apps.api.src.modules.ingestion.application.use_cases.create_ingestion_job import (
    CreateIngestionJob,
)
from apps.api.src.modules.ingestion.domain.entities import Chunk, Document, IngestionJob
from apps.api.src.modules.ingestion.domain.enums import (
    DocumentSourceType,
    IngestionJobStatus,
)
from apps.api.src.modules.ingestion.domain.exceptions import IngestionTaskDispatchError
from apps.api.src.modules.ingestion.domain.repositories import (
    ChunkRepository,
    DocumentRepository,
    IngestionJobRepository,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeJobRepo(IngestionJobRepository):
    def __init__(self) -> None:
        self._jobs: dict[UUID, IngestionJob] = {}

    async def save(self, job: IngestionJob) -> None:
        self._jobs[job.id] = job

    async def get_by_id(self, job_id: UUID) -> IngestionJob | None:
        return self._jobs.get(job_id)

    async def get_by_scraping_result_id(self, scraping_result_id: UUID) -> IngestionJob | None:
        return None


class FakeDocRepo(DocumentRepository):
    async def save(self, document: Document) -> None:
        pass

    async def get_by_id(self, document_id: UUID) -> Document | None:
        return None

    async def find_by_content_hash(self, content_hash: str) -> Document | None:
        return None


class FakeChunkRepo(ChunkRepository):
    async def save(self, chunk: Chunk) -> None:
        pass

    async def list_by_document_id(self, document_id: UUID) -> list[Chunk]:
        return []


class FakeUoW(IngestionUnitOfWork):
    def __init__(self, job_repo: FakeJobRepo) -> None:
        self.job_repository = job_repo
        self.document_repository = FakeDocRepo()
        self.chunk_repository = FakeChunkRepo()
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


class FakeDispatcher(IngestionTaskDispatcher):
    def __init__(self, should_fail: bool = False) -> None:
        self._should_fail = should_fail
        self.dispatched: list[UUID] = []

    async def dispatch(self, *, job_id: UUID) -> None:
        if self._should_fail:
            raise IngestionTaskDispatchError("redis fora do ar")
        self.dispatched.append(job_id)


def _make_use_case(
    should_fail_dispatch: bool = False,
) -> tuple[CreateIngestionJob, FakeJobRepo, FakeDispatcher]:
    job_repo = FakeJobRepo()
    dispatcher = FakeDispatcher(should_fail=should_fail_dispatch)
    uow = FakeUoW(job_repo)
    use_case = CreateIngestionJob(
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
    result_id = uuid4()

    view = await use_case.execute(CreateIngestionJobInput(scraping_result_id=result_id))

    saved = await job_repo.get_by_id(view.id)
    assert saved is not None
    assert saved.status is IngestionJobStatus.PENDING
    assert saved.scraping_result_id == result_id
    assert saved.source_type is DocumentSourceType.STARTUP_EVIDENCE


@pytest.mark.anyio
async def test_creates_job_with_source_type() -> None:
    use_case, job_repo, _ = _make_use_case()
    result_id = uuid4()

    view = await use_case.execute(
        CreateIngestionJobInput(
            scraping_result_id=result_id,
            source_type=DocumentSourceType.NVIDIA_KNOWLEDGE,
        )
    )

    saved = await job_repo.get_by_id(view.id)
    assert saved is not None
    assert saved.source_type is DocumentSourceType.NVIDIA_KNOWLEDGE
    assert view.source_type is DocumentSourceType.NVIDIA_KNOWLEDGE


@pytest.mark.anyio
async def test_dispatches_job_id_to_queue() -> None:
    use_case, _, dispatcher = _make_use_case()

    view = await use_case.execute(CreateIngestionJobInput(scraping_result_id=uuid4()))

    assert view.id in dispatcher.dispatched


@pytest.mark.anyio
async def test_fails_job_when_dispatch_fails() -> None:
    use_case, job_repo, _ = _make_use_case(should_fail_dispatch=True)

    with pytest.raises(IngestionTaskDispatchError):
        await use_case.execute(CreateIngestionJobInput(scraping_result_id=uuid4()))

    all_jobs = list(job_repo._jobs.values())
    assert len(all_jobs) == 1
    assert all_jobs[0].status is IngestionJobStatus.FAILED


@pytest.mark.anyio
async def test_returns_job_view_with_scraping_result_id() -> None:
    use_case, _, _ = _make_use_case()
    result_id = uuid4()

    view = await use_case.execute(CreateIngestionJobInput(scraping_result_id=result_id))

    assert view.scraping_result_id == result_id
    assert view.source_type is DocumentSourceType.STARTUP_EVIDENCE
    assert view.status is IngestionJobStatus.PENDING
    assert view.document_id is None
