"""Testes do comportamento do caso de uso CreateScrapingJob."""

from datetime import timedelta
from uuid import uuid4

import pytest

from apps.api.src.modules.scraping.application.ports import TaskDispatcher
from apps.api.src.modules.scraping.application.unit_of_work import ScrapingUnitOfWork
from apps.api.src.modules.scraping.application.use_cases.create_scraping_job import (
    CreateScrapingJob,
)
from apps.api.src.modules.scraping.domain.entities import ScrapingResult, utc_now
from apps.api.src.modules.scraping.domain.enums import JobStatus, ScrapingMethod
from apps.api.src.modules.scraping.domain.exceptions import TaskDispatchError
from apps.api.src.modules.scraping.domain.policies import SCRAPING_RESULT_CACHE_TTL
from apps.api.src.modules.scraping.infrastructure.repositories.in_memory_attempt_repository import (
    InMemoryScrapingAttemptRepository,
)
from apps.api.src.modules.scraping.infrastructure.repositories.in_memory_job_repository import (
    InMemoryScrapingJobRepository,
)
from apps.api.src.modules.scraping.infrastructure.repositories.in_memory_result_repository import (
    InMemoryScrapingResultRepository,
)


class InMemoryUnitOfWork(ScrapingUnitOfWork):
    """Unit of Work minima para testar persistencia do estado do job."""

    def __init__(self, jobs, attempts, results) -> None:
        self.job_repository = jobs
        self.attempt_repository = attempts
        self.result_repository = results

    async def __aenter__(self):
        return self

    async def __aexit__(self, exception_type, exception, traceback) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FailingDispatcher(TaskDispatcher):
    """Simula uma fila indisponivel depois que o job foi persistido."""

    async def dispatch(self, job_id) -> None:
        raise TaskDispatchError("Fila indisponivel.")


class RecordingDispatcher(TaskDispatcher):
    """Registra os job_ids despachados, sem falhar."""

    def __init__(self) -> None:
        self.dispatched_job_ids: list = []

    async def dispatch(self, job_id) -> None:
        self.dispatched_job_ids.append(job_id)


def _make_approved_result(url: str, *, created_at) -> ScrapingResult:
    return ScrapingResult(
        job_id=uuid4(),
        url=url,
        final_url=url,
        title="Startup Example",
        raw_html="<html></html>",
        raw_text="conteudo aprovado anteriormente",
        method=ScrapingMethod.BEAUTIFULSOUP,
        status_code=200,
        technical_score=1.0,
        text_score=1.0,
        evidence_score=1.0,
        quality_score=1.0,
        content_hash=uuid4().hex,
        created_at=created_at,
    )


@pytest.mark.anyio
async def test_dispatch_failure_is_persisted_on_job() -> None:
    """Job deve registrar falha quando nao consegue chegar ao worker."""

    jobs = InMemoryScrapingJobRepository()
    attempts = InMemoryScrapingAttemptRepository()
    results = InMemoryScrapingResultRepository()
    use_case = CreateScrapingJob(
        unit_of_work_factory=lambda: InMemoryUnitOfWork(jobs, attempts, results),
        task_dispatcher=FailingDispatcher(),
    )

    with pytest.raises(TaskDispatchError):
        await use_case.execute("https://example.com")

    persisted_jobs = list(jobs._jobs.values())
    assert len(persisted_jobs) == 1
    assert persisted_jobs[0].status is JobStatus.FAILED
    assert persisted_jobs[0].error_message == "Fila indisponivel."


@pytest.mark.anyio
async def test_reuses_recent_result_for_same_url_without_dispatching() -> None:
    """URL ja raspada com sucesso dentro do TTL nao deve ser raspada de novo."""

    url = "https://startup.example.com"
    jobs = InMemoryScrapingJobRepository()
    attempts = InMemoryScrapingAttemptRepository()
    results = InMemoryScrapingResultRepository()
    cached_result = _make_approved_result(url, created_at=utc_now())
    await results.save(cached_result)

    dispatcher = RecordingDispatcher()
    use_case = CreateScrapingJob(
        unit_of_work_factory=lambda: InMemoryUnitOfWork(jobs, attempts, results),
        task_dispatcher=dispatcher,
    )

    job = await use_case.execute(url)

    assert job.status is JobStatus.COMPLETED
    assert job.result_id == cached_result.id
    assert dispatcher.dispatched_job_ids == []


@pytest.mark.anyio
async def test_result_outside_cache_window_triggers_new_scraping() -> None:
    """URL raspada ha mais tempo que o TTL deve raspar de novo normalmente."""

    url = "https://startup.example.com"
    jobs = InMemoryScrapingJobRepository()
    attempts = InMemoryScrapingAttemptRepository()
    results = InMemoryScrapingResultRepository()
    stale_result = _make_approved_result(
        url, created_at=utc_now() - SCRAPING_RESULT_CACHE_TTL - timedelta(hours=1)
    )
    await results.save(stale_result)

    dispatcher = RecordingDispatcher()
    use_case = CreateScrapingJob(
        unit_of_work_factory=lambda: InMemoryUnitOfWork(jobs, attempts, results),
        task_dispatcher=dispatcher,
    )

    job = await use_case.execute(url)

    assert job.status is JobStatus.PENDING
    assert job.result_id is None
    assert dispatcher.dispatched_job_ids == [job.id]
