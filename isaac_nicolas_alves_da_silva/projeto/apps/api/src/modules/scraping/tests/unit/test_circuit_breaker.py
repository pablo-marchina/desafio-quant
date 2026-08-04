"""Testes do circuit breaker por domínio no scraping.

Cobre a política `is_circuit_open()` e o filtro `_apply_circuit_breaker()`
da pipeline, usando um repositório configurável que devolve contagens de
falha sem precisar de banco real.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.api.src.modules.scraping.application.dto import (
    DeterministicValidationResult,
    ScrapingOutput,
)
from apps.api.src.modules.scraping.application.ports import (
    DeterministicValidator,
    Scraper,
)
from apps.api.src.modules.scraping.application.quality_scoring_service import (
    QualityScoringService,
)
from apps.api.src.modules.scraping.application.scraping_pipeline import (
    ScrapingPipeline,
)
from apps.api.src.modules.scraping.application.strategy_selector import (
    ScrapingStrategySelector,
)
from apps.api.src.modules.scraping.domain.entities import ScrapingAttempt
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.domain.exceptions import ScrapingFailedError
from apps.api.src.modules.scraping.domain.policies import (
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    ValidationDecisionPolicy,
    is_circuit_open,
)
from apps.api.src.modules.scraping.domain.repositories import (
    ScrapingAttemptRepository,
)
from apps.api.src.modules.scraping.infrastructure.repositories.in_memory_attempt_repository import (
    InMemoryScrapingAttemptRepository,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class ConfigurableAttemptRepo(ScrapingAttemptRepository):
    """Repositório que devolve contagens de falha configuráveis por teste."""

    def __init__(self, failure_counts: dict[tuple[str, ScrapingMethod], int] | None = None) -> None:
        self._inner = InMemoryScrapingAttemptRepository()
        self._failure_counts: dict[tuple[str, ScrapingMethod], int] = failure_counts or {}

    async def save(self, attempt: ScrapingAttempt) -> None:
        await self._inner.save(attempt)

    async def list_by_job_id(self, job_id):
        return await self._inner.list_by_job_id(job_id)

    async def count_recent_failures_by_host_and_method(
        self, host: str, method: ScrapingMethod, since: datetime
    ) -> int:
        return self._failure_counts.get((host, method), 0)


class AlwaysGoodScraper(Scraper):
    def __init__(self, method: ScrapingMethod) -> None:
        self.method = method
        self.call_count = 0

    async def scrape(self, scraping_input) -> ScrapingOutput:
        self.call_count += 1
        return ScrapingOutput(
            source_url=scraping_input.url,
            final_url=scraping_input.url,
            title="Startup",
            raw_html="<html>startup conteudo</html>",
            raw_text="startup conteudo aprovado",
            status_code=200,
            content_type="text/html",
            method=self.method,
        )


class AlwaysGoodValidator(DeterministicValidator):
    async def validate(self, output: ScrapingOutput) -> DeterministicValidationResult:
        return DeterministicValidationResult(
            technical_score=1.0,
            text_score=0.90,
            evidence_score=0.80,
        )


def _make_pipeline(
    scrapers: list[Scraper],
    attempt_repo: ScrapingAttemptRepository,
) -> ScrapingPipeline:
    from apps.api.src.modules.scraping.domain.policies import (
        ContentAcceptancePolicy,
        FallbackPolicy,
    )

    return ScrapingPipeline(
        strategy_selector=ScrapingStrategySelector(scrapers),
        validator=AlwaysGoodValidator(),
        scoring_service=QualityScoringService(),
        decision_policy=ValidationDecisionPolicy(
            acceptance_policy=ContentAcceptancePolicy(),
            fallback_policy=FallbackPolicy(),
        ),
        attempt_repository=attempt_repo,
    )


# ---------------------------------------------------------------------------
# Testes de políticas
# ---------------------------------------------------------------------------


def test_circuit_open_at_threshold() -> None:
    assert is_circuit_open(CIRCUIT_BREAKER_FAILURE_THRESHOLD) is True


def test_circuit_open_above_threshold() -> None:
    assert is_circuit_open(CIRCUIT_BREAKER_FAILURE_THRESHOLD + 5) is True


def test_circuit_closed_below_threshold() -> None:
    assert is_circuit_open(CIRCUIT_BREAKER_FAILURE_THRESHOLD - 1) is False


def test_circuit_closed_at_zero() -> None:
    assert is_circuit_open(0) is False


# ---------------------------------------------------------------------------
# Testes de integração do circuit breaker na pipeline
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_circuit_breaker_skips_tripped_strategy() -> None:
    """Estratégia com circuito aberto não deve ser chamada."""

    bs4 = AlwaysGoodScraper(ScrapingMethod.BEAUTIFULSOUP)
    playwright = AlwaysGoodScraper(ScrapingMethod.PLAYWRIGHT)

    host = "example.com"
    repo = ConfigurableAttemptRepo(
        failure_counts={(host, ScrapingMethod.BEAUTIFULSOUP): CIRCUIT_BREAKER_FAILURE_THRESHOLD}
    )
    pipeline = _make_pipeline([bs4, playwright], repo)

    await pipeline.execute(uuid4(), f"https://{host}/startup")

    # BS4 estava tripped — nunca deve ter sido chamado
    assert bs4.call_count == 0
    # Playwright (circuito fechado) foi chamado
    assert playwright.call_count == 1


@pytest.mark.anyio
async def test_circuit_breaker_does_not_skip_below_threshold() -> None:
    """Estratégia com menos falhas do que o limiar deve ser tentada normalmente."""

    bs4 = AlwaysGoodScraper(ScrapingMethod.BEAUTIFULSOUP)

    host = "example.com"
    repo = ConfigurableAttemptRepo(
        failure_counts={(host, ScrapingMethod.BEAUTIFULSOUP): CIRCUIT_BREAKER_FAILURE_THRESHOLD - 1}
    )
    pipeline = _make_pipeline([bs4], repo)

    await pipeline.execute(uuid4(), f"https://{host}/startup")

    assert bs4.call_count == 1


@pytest.mark.anyio
async def test_circuit_breaker_fallback_when_all_tripped() -> None:
    """Quando todos os circuitos estão abertos, a lista completa é usada (fallback)."""

    bs4 = AlwaysGoodScraper(ScrapingMethod.BEAUTIFULSOUP)
    playwright = AlwaysGoodScraper(ScrapingMethod.PLAYWRIGHT)

    host = "example.com"
    threshold = CIRCUIT_BREAKER_FAILURE_THRESHOLD
    repo = ConfigurableAttemptRepo(
        failure_counts={
            (host, ScrapingMethod.BEAUTIFULSOUP): threshold,
            (host, ScrapingMethod.PLAYWRIGHT): threshold,
        }
    )
    pipeline = _make_pipeline([bs4, playwright], repo)

    # Não deve levantar — o fallback usa a lista completa quando tudo está tripped
    result = await pipeline.execute(uuid4(), f"https://{host}/startup")

    assert result is not None
    # Pelo menos um dos scrapers foi chamado
    assert bs4.call_count + playwright.call_count >= 1


@pytest.mark.anyio
async def test_circuit_breaker_uses_host_not_full_url() -> None:
    """Circuito é avaliado por host — paths diferentes do mesmo host são afetados."""

    bs4 = AlwaysGoodScraper(ScrapingMethod.BEAUTIFULSOUP)
    playwright = AlwaysGoodScraper(ScrapingMethod.PLAYWRIGHT)

    host = "docs.nvidia.com"
    threshold = CIRCUIT_BREAKER_FAILURE_THRESHOLD
    repo = ConfigurableAttemptRepo(
        failure_counts={(host, ScrapingMethod.BEAUTIFULSOUP): threshold}
    )
    pipeline = _make_pipeline([bs4, playwright], repo)

    # URL com path diferente — circuito ainda está aberto para BS4 neste host
    await pipeline.execute(uuid4(), f"https://{host}/tensorrt/guide.html")

    assert bs4.call_count == 0
    assert playwright.call_count == 1


@pytest.mark.anyio
async def test_circuit_breaker_different_hosts_are_independent() -> None:
    """Falhas em um host não abrem o circuito para outros hosts."""

    bs4 = AlwaysGoodScraper(ScrapingMethod.BEAUTIFULSOUP)

    repo = ConfigurableAttemptRepo(
        failure_counts={
            ("bad-host.com", ScrapingMethod.BEAUTIFULSOUP): CIRCUIT_BREAKER_FAILURE_THRESHOLD
        }
    )
    pipeline = _make_pipeline([bs4], repo)

    # Host diferente — circuito fechado, BS4 deve ser chamado
    await pipeline.execute(uuid4(), "https://good-host.com/startup")

    assert bs4.call_count == 1
