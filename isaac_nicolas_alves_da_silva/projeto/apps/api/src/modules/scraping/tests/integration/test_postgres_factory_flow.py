"""Teste do fluxo montado pela factory contra o PostgreSQL real."""

import httpx
import pytest
from sqlalchemy import delete

from apps.api.src.database.relational.session import AsyncSessionFactory, engine
from apps.api.src.modules.scraping.application.quality_scoring_service import (
    QualityScoringService,
)
from apps.api.src.modules.scraping.application.scraping_pipeline import (
    ScrapingPipeline,
)
from apps.api.src.modules.scraping.application.strategy_selector import (
    ScrapingStrategySelector,
)
from apps.api.src.modules.scraping.domain.enums import AttemptStatus, JobStatus
from apps.api.src.modules.scraping.domain.policies import (
    ContentAcceptancePolicy,
    FallbackPolicy,
    ValidationDecisionPolicy,
)
from apps.api.src.modules.scraping.factories.scraping_factory import ScrapingFactory
from apps.api.src.modules.scraping.infrastructure.database.models import (
    ScrapingJobModel,
)
from apps.api.src.shared.queue.dramatiq_broker import broker
from apps.api.src.modules.scraping.infrastructure.scrapers.beautifulsoup_scraper import (
    BeautifulSoupScraper,
)
from apps.api.src.modules.scraping.infrastructure.validators.deterministic_validator import (
    BasicDeterministicValidator,
)


class AllowPublicUrlGuard:
    """Evita depender de DNS real durante este teste integrado."""

    async def validate(self, url: str) -> None:
        return None


def make_http_client() -> httpx.AsyncClient:
    """Devolve uma pagina previsivel sem realizar uma requisicao externa."""

    paragraph = (
        "A startup utiliza inteligencia artificial, machine learning e "
        "computer vision para analisar imagens industriais em tempo real. "
    )
    html = f"""
    <html>
      <head><title>Factory PostgreSQL Flow</title></head>
      <body><h1>Plataforma de IA</h1><p>{paragraph * 18}</p></body>
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


def create_test_pipeline(attempt_repository) -> ScrapingPipeline:
    """Monta a pipeline deterministica mantendo o repositorio PostgreSQL."""

    scraper = BeautifulSoupScraper(
        url_guard=AllowPublicUrlGuard(),
        client_factory=make_http_client,
    )

    return ScrapingPipeline(
        strategy_selector=ScrapingStrategySelector([scraper]),
        validator=BasicDeterministicValidator(),
        scoring_service=QualityScoringService(),
        decision_policy=ValidationDecisionPolicy(
            ContentAcceptancePolicy(),
            FallbackPolicy(),
        ),
        attempt_repository=attempt_repository,
    )


@pytest.mark.anyio
async def test_factory_persists_complete_flow_in_postgres(monkeypatch) -> None:
    """API publica o job pending e o worker conclui o fluxo no PostgreSQL."""

    # Trocamos apenas a coleta HTTP. Factory, casos de uso, Unit of Work,
    # repositorios e PostgreSQL continuam sendo os componentes reais.
    monkeypatch.setattr(
        ScrapingFactory,
        "create_pipeline",
        staticmethod(create_test_pipeline),
    )

    published_messages = []

    def capture_message(message):
        published_messages.append(message)
        return message

    # Capturamos a publicacao para nao exigir um worker durante o teste. O
    # dispatcher e a mensagem Dramatiq continuam sendo os componentes reais.
    monkeypatch.setattr(broker, "enqueue", capture_message)

    created_job = None

    try:
        create_job = ScrapingFactory.create_create_scraping_job()
        created_job = await create_job.execute("https://factory-test.example")

        pending_details = await ScrapingFactory.create_get_scraping_job().execute(
            created_job.id
        )

        assert pending_details.job.status is JobStatus.PENDING
        assert len(published_messages) == 1
        assert published_messages[0].actor_name == "execute_scraping_job"
        assert published_messages[0].args == (str(created_job.id),)

        # Simula o worker consumindo a mensagem publicada pela API.
        await ScrapingFactory.create_execute_scraping_job().execute(created_job.id)

        details = await ScrapingFactory.create_get_scraping_job().execute(
            created_job.id
        )
        result = await ScrapingFactory.create_get_scraping_result().execute(
            details.job.result_id
        )

        assert details.job.status is JobStatus.COMPLETED
        assert len(details.attempts) == 1
        assert details.attempts[0].status is AttemptStatus.ACCEPTED
        assert result.job_id == created_job.id
        assert result.title == "Factory PostgreSQL Flow"
    finally:
        # O fluxo usa commits reais. Removemos o job ao final e o CASCADE do
        # banco remove automaticamente sua tentativa e seu resultado.
        if created_job is not None:
            async with AsyncSessionFactory() as session:
                await session.execute(
                    delete(ScrapingJobModel).where(
                        ScrapingJobModel.id == created_job.id
                    )
                )
                await session.commit()

        # Fecha conexoes do pool antes que o AnyIO encerre o event loop deste
        # teste. Isso evita reutilizar no proximo teste uma conexao ligada a um
        # loop que ja foi fechado pelo Windows.
        await engine.dispose()
