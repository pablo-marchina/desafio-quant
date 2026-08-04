"""Teste integrado do primeiro fluxo vertical do módulo de scraping."""

import httpx
import pytest

from apps.api.src.modules.scraping.application.quality_scoring_service import (
    QualityScoringService,
)
from apps.api.src.modules.scraping.application.scraping_pipeline import (
    ScrapingPipeline,
)
from apps.api.src.modules.scraping.application.strategy_selector import (
    ScrapingStrategySelector,
)
from apps.api.src.modules.scraping.application.unit_of_work import ScrapingUnitOfWork
from apps.api.src.modules.scraping.application.use_cases.create_scraping_job import (
    CreateScrapingJob,
)
from apps.api.src.modules.scraping.application.use_cases.execute_scraping_job import (
    ExecuteScrapingJob,
)
from apps.api.src.modules.scraping.application.use_cases.get_scraping_job import (
    GetScrapingJob,
)
from apps.api.src.modules.scraping.application.use_cases.get_scraping_result import (
    GetScrapingResult,
)
from apps.api.src.modules.scraping.domain.enums import AttemptStatus, JobStatus
from apps.api.src.modules.scraping.domain.policies import (
    ContentAcceptancePolicy,
    FallbackPolicy,
    ValidationDecisionPolicy,
)
from apps.api.src.modules.scraping.infrastructure.queue.local_task_dispatcher import (
    LocalTaskDispatcher,
)
from apps.api.src.modules.scraping.infrastructure.repositories.in_memory_attempt_repository import (
    InMemoryScrapingAttemptRepository,
)
from apps.api.src.modules.scraping.infrastructure.repositories.in_memory_job_repository import (
    InMemoryScrapingJobRepository,
)
from apps.api.src.modules.scraping.infrastructure.repositories.in_memory_result_repository import (
    InMemoryScrapingResultRepository,
)
from apps.api.src.modules.scraping.infrastructure.scrapers.beautifulsoup_scraper import (
    BeautifulSoupScraper,
)
from apps.api.src.modules.scraping.infrastructure.validators.deterministic_validator import (
    BasicDeterministicValidator,
)


class AllowPublicUrlGuard:
    """Evita DNS real mantendo a etapa de validação no fluxo."""

    async def validate(self, url: str) -> None:
        return None


class InMemoryUnitOfWork(ScrapingUnitOfWork):
    """Unit of Work simples usada apenas pelo fluxo integrado em memoria."""

    def __init__(self, jobs, attempts, results) -> None:
        self.job_repository = jobs
        self.attempt_repository = attempts
        self.result_repository = results

    async def __aenter__(self):
        return self

    async def __aexit__(self, exception_type, exception, traceback) -> None:
        await self.rollback()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def make_http_client() -> httpx.AsyncClient:
    """Simula uma página pública com conteúdo suficiente e evidências de IA."""

    paragraph = (
        "A startup utiliza inteligência artificial, machine learning e "
        "computer vision para analisar imagens industriais em tempo real. "
    )
    html = f"""
    <html>
      <head><title>Startup Industrial AI</title></head>
      <body>
        <h1>Plataforma de visão computacional</h1>
        <p>{paragraph * 18}</p>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=html,
            request=request,
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.anyio
async def test_complete_scraping_flow_creates_job_result_and_attempt() -> None:
    """Criação deve disparar execução e disponibilizar status e resultado."""

    jobs = InMemoryScrapingJobRepository()
    attempts = InMemoryScrapingAttemptRepository()
    results = InMemoryScrapingResultRepository()

    scraper = BeautifulSoupScraper(
        url_guard=AllowPublicUrlGuard(),
        client_factory=make_http_client,
    )
    pipeline = ScrapingPipeline(
        strategy_selector=ScrapingStrategySelector([scraper]),
        validator=BasicDeterministicValidator(),
        scoring_service=QualityScoringService(),
        decision_policy=ValidationDecisionPolicy(
            ContentAcceptancePolicy(),
            FallbackPolicy(),
        ),
        attempt_repository=attempts,
    )
    execute_job = ExecuteScrapingJob(
        unit_of_work_factory=lambda: InMemoryUnitOfWork(jobs, attempts, results),
        pipeline_factory=lambda attempt_repository: pipeline,
    )

    async def execute_locally(job_id) -> None:
        await execute_job.execute(job_id)

    create_job = CreateScrapingJob(
        unit_of_work_factory=lambda: InMemoryUnitOfWork(jobs, attempts, results),
        task_dispatcher=LocalTaskDispatcher(execute_locally),
    )

    created_job = await create_job.execute("https://example.com")
    details = await GetScrapingJob(
        lambda: InMemoryUnitOfWork(jobs, attempts, results)
    ).execute(created_job.id)
    result = await GetScrapingResult(
        lambda: InMemoryUnitOfWork(jobs, attempts, results)
    ).execute(details.job.result_id)

    assert details.job.status is JobStatus.COMPLETED
    assert details.job.result_id == result.id
    assert len(details.attempts) == 1
    assert details.attempts[0].status is AttemptStatus.ACCEPTED
    assert result.title == "Startup Industrial AI"
    assert "visão computacional" in result.raw_text
    assert result.quality_score >= 0.75
