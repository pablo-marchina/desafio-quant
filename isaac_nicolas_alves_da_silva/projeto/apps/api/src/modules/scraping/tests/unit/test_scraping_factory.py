"""Testes da composicao concreta do modulo de scraping."""

from types import SimpleNamespace

import apps.api.src.modules.agents.factories.agents_factory as agents_factory_module
import apps.api.src.modules.scraping.factories.scraping_factory as factory_module
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.factories.scraping_factory import ScrapingFactory
from apps.api.src.modules.scraping.infrastructure.agent_adapters.agents_semantic_investigator import (
    AgentsSemanticInvestigator,
)
from apps.api.src.modules.scraping.infrastructure.repositories.in_memory_attempt_repository import (
    InMemoryScrapingAttemptRepository,
)


def test_factory_configures_strategies_by_cost_and_specialization() -> None:
    """Extracao especializada deve acontecer antes do fallback com navegador."""

    pipeline = ScrapingFactory.create_pipeline(InMemoryScrapingAttemptRepository())
    strategies = pipeline.strategy_selector.select("https://example.com")

    assert [strategy.method for strategy in strategies] == [
        ScrapingMethod.BEAUTIFULSOUP,
        ScrapingMethod.TRAFILATURA,
        ScrapingMethod.PLAYWRIGHT,
    ]


def test_factory_enables_gemini_only_when_api_key_exists(monkeypatch) -> None:
    """A revisao semantica deve ser opt-in para evitar custo acidental."""

    monkeypatch.setattr(
        factory_module,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="secret",
            gemini_model="gemini-test",
            scraping_startup_timeout_seconds=90.0,
            scraping_reference_timeout_seconds=120.0,
            firecrawl_api_key="",
        ),
    )
    # AgentsFactory tem sua propria importacao de get_settings: sem o
    # monkeypatch abaixo, ela leria as settings reais do ambiente.
    monkeypatch.setattr(
        agents_factory_module,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="secret",
            gemini_model="gemini-test",
        ),
    )

    pipeline = ScrapingFactory.create_pipeline(InMemoryScrapingAttemptRepository())

    assert pipeline.semantic_validator is not None
    assert pipeline.semantic_validator.model == "gemini-test"
    assert isinstance(pipeline.semantic_investigator, AgentsSemanticInvestigator)
    assert pipeline.semantic_investigator.evidence_validation_service.model == (
        "gemini-test"
    )


def test_factory_disables_agent_investigator_without_gemini_key(monkeypatch) -> None:
    """Sem chave Gemini, nem semantic_validator nem semantic_investigator existem."""

    monkeypatch.setattr(
        factory_module,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="",
            gemini_model="gemini-test",
            scraping_startup_timeout_seconds=90.0,
            scraping_reference_timeout_seconds=120.0,
            firecrawl_api_key="",
        ),
    )
    monkeypatch.setattr(
        agents_factory_module,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key="", gemini_model="gemini-test"),
    )

    pipeline = ScrapingFactory.create_pipeline(InMemoryScrapingAttemptRepository())

    assert pipeline.semantic_validator is None
    assert pipeline.semantic_investigator is None
