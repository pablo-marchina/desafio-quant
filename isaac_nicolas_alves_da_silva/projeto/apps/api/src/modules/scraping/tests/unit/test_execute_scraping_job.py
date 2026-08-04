"""Testes do comportamento do caso de uso ExecuteScrapingJob."""

from uuid import uuid4

import pytest

from apps.api.src.modules.scraping.application.unit_of_work import ScrapingUnitOfWork
from apps.api.src.modules.scraping.application.use_cases.execute_scraping_job import (
    ExecuteScrapingJob,
)
from apps.api.src.modules.scraping.domain.entities import ScrapingJob, ScrapingResult
from apps.api.src.modules.scraping.domain.enums import JobStatus, ScrapingMethod
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
    """Unit of Work minima para testar o caso de uso sem PostgreSQL."""

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


def create_result(job_id, *, content_hash: str) -> ScrapingResult:
    """Cria um resultado aceito para simular a saida da pipeline."""

    return ScrapingResult(
        job_id=job_id,
        url="https://example.com",
        final_url="https://example.com",
        title="Example",
        raw_html="<html>Example</html>",
        raw_text="Example",
        method=ScrapingMethod.BEAUTIFULSOUP,
        status_code=200,
        technical_score=1.0,
        text_score=1.0,
        evidence_score=1.0,
        quality_score=1.0,
        content_hash=content_hash,
    )


@pytest.mark.anyio
async def test_duplicate_message_does_not_execute_completed_job() -> None:
    """Redelivery de um job terminal deve ser ignorada com seguranca."""

    jobs = InMemoryScrapingJobRepository()
    attempts = InMemoryScrapingAttemptRepository()
    results = InMemoryScrapingResultRepository()
    job = ScrapingJob(url="https://example.com")
    job.start()
    job.complete(uuid4())
    await jobs.save(job)

    pipeline_was_called = False

    def create_pipeline(attempt_repository):
        nonlocal pipeline_was_called
        pipeline_was_called = True
        raise AssertionError("A pipeline nao deveria ser criada.")

    use_case = ExecuteScrapingJob(
        unit_of_work_factory=lambda: InMemoryUnitOfWork(jobs, attempts, results),
        pipeline_factory=create_pipeline,
    )

    restored_job = await use_case.execute(job.id)

    assert restored_job.status is JobStatus.COMPLETED
    assert pipeline_was_called is False
    assert await attempts.list_by_job_id(job.id) == []


@pytest.mark.anyio
async def test_duplicate_content_fails_job_without_saving_second_result() -> None:
    """Um hash existente deve impedir que outro resultado seja persistido."""

    jobs = InMemoryScrapingJobRepository()
    attempts = InMemoryScrapingAttemptRepository()
    results = InMemoryScrapingResultRepository()
    job = ScrapingJob(url="https://example.com")
    await jobs.save(job)

    existing_result = create_result(uuid4(), content_hash="same-hash")
    await results.save(existing_result)

    class PipelineStub:
        async def execute(self, job_id, url, *, source_type="startup_evidence"):
            return create_result(job_id, content_hash="same-hash")

    use_case = ExecuteScrapingJob(
        unit_of_work_factory=lambda: InMemoryUnitOfWork(jobs, attempts, results),
        pipeline_factory=lambda attempt_repository: PipelineStub(),
    )

    restored_job = await use_case.execute(job.id)

    assert restored_job.status is JobStatus.FAILED
    assert str(existing_result.id) in restored_job.error_message
    assert await results.get_by_content_hash("same-hash") == existing_result
