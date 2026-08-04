"""Teste integrado da API, Redis, worker Dramatiq e PostgreSQL reais."""

import asyncio
from uuid import uuid4

import dramatiq
import httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from apps.api.src.config.settings import get_settings
from apps.api.src.modules.scraping.application.quality_scoring_service import (
    QualityScoringService,
)
from apps.api.src.modules.scraping.application.scraping_pipeline import (
    ScrapingPipeline,
)
from apps.api.src.modules.scraping.application.strategy_selector import (
    ScrapingStrategySelector,
)
from apps.api.src.modules.scraping.domain.enums import JobStatus
from apps.api.src.modules.scraping.domain.policies import (
    ContentAcceptancePolicy,
    FallbackPolicy,
    ValidationDecisionPolicy,
)
from apps.api.src.modules.scraping.factories.scraping_factory import ScrapingFactory
from apps.api.src.modules.scraping.infrastructure.database.models import (
    ScrapingJobModel,
)
from apps.api.src.modules.scraping.infrastructure.database.postgres_unit_of_work import (
    PostgresScrapingUnitOfWork,
)
from apps.api.src.shared.queue.dramatiq_broker import broker
from apps.api.src.modules.scraping.infrastructure.scrapers.beautifulsoup_scraper import (
    BeautifulSoupScraper,
)
from apps.api.src.modules.scraping.infrastructure.validators.deterministic_validator import (
    BasicDeterministicValidator,
)

# Importar tasks registra o actor que o worker consumira.
from workers.scraper_worker import tasks as _tasks  # noqa: F401


class AllowPublicUrlGuard:
    """Evita DNS real mantendo o restante do fluxo distribuido."""

    async def validate(self, url: str) -> None:
        return None


def make_http_client() -> httpx.AsyncClient:
    """Devolve conteudo deterministico suficiente para ser aceito."""

    paragraph = (
        "A startup utiliza inteligencia artificial, machine learning e "
        "computer vision para analisar imagens industriais em tempo real. "
    )
    html = (
        "<html><head><title>Distributed Worker Flow</title></head>"
        f"<body><p>{paragraph * 18}</p></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=html,
            request=request,
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def create_test_pipeline(attempt_repository) -> ScrapingPipeline:
    """Monta pipeline previsivel mantendo fila e banco reais."""

    return ScrapingPipeline(
        strategy_selector=ScrapingStrategySelector(
            [
                BeautifulSoupScraper(
                    url_guard=AllowPublicUrlGuard(),
                    client_factory=make_http_client,
                )
            ]
        ),
        validator=BasicDeterministicValidator(),
        scoring_service=QualityScoringService(),
        decision_policy=ValidationDecisionPolicy(
            ContentAcceptancePolicy(),
            FallbackPolicy(),
        ),
        attempt_repository=attempt_repository,
    )


@pytest.mark.anyio
async def test_redis_worker_completes_persisted_job(monkeypatch) -> None:
    """Mensagem real no Redis deve ser consumida pelo worker e concluir o job."""

    test_queue = f"scraping-test-{uuid4()}"
    test_engine = create_async_engine(
        get_settings().database_url,
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    monkeypatch.setattr(
        ScrapingFactory,
        "create_unit_of_work",
        staticmethod(lambda: PostgresScrapingUnitOfWork(session_factory)),
    )
    monkeypatch.setattr(
        ScrapingFactory,
        "create_pipeline",
        staticmethod(create_test_pipeline),
    )

    # Publica a mensagem real em uma fila exclusiva deste teste.
    original_enqueue = broker.enqueue

    def enqueue_in_test_queue(message, *, delay=None):
        return original_enqueue(
            message.copy(queue_name=test_queue),
            delay=delay,
        )

    monkeypatch.setattr(broker, "enqueue", enqueue_in_test_queue)

    # Actors declaram suas filas no decorator. Como este teste cria uma fila
    # exclusiva dinamicamente, precisamos declara-la antes de iniciar o worker.
    broker.declare_queue(test_queue)

    worker = dramatiq.Worker(
        broker,
        queues={test_queue},
        worker_threads=1,
    )
    worker.start()
    created_job = None

    try:
        created_job = await ScrapingFactory.create_create_scraping_job().execute(
            "https://distributed-test.example"
        )
        assert created_job.status is JobStatus.PENDING

        # O consumidor move a mensagem do Redis para sua fila interna de forma
        # concorrente. Consultamos o estado persistido, como a API faria.
        for _ in range(50):
            details = await ScrapingFactory.create_get_scraping_job().execute(
                created_job.id
            )
            if details.job.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
                break
            await asyncio.sleep(0.1)
        else:
            pytest.fail("O worker nao concluiu o job dentro do tempo esperado.")

        assert details.job.status is JobStatus.COMPLETED
        result = await ScrapingFactory.create_get_scraping_result().execute(
            details.job.result_id
        )

        assert len(details.attempts) == 1
        assert result.title == "Distributed Worker Flow"
    finally:
        await asyncio.to_thread(worker.stop)

        if created_job is not None:
            async with session_factory() as session:
                await session.execute(
                    delete(ScrapingJobModel).where(
                        ScrapingJobModel.id == created_job.id
                    )
                )
                await session.commit()

        await test_engine.dispose()
