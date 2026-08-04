"""Testes de composicao da AgentsFactory."""

from types import SimpleNamespace

from apps.api.src.modules.agents.factories import agents_factory as factory_module
from apps.api.src.modules.agents.graphs.evidence_validation.graph import (
    EvidenceValidationGraph,
)
from apps.api.src.modules.agents.graphs.search_planning.graph import (
    SearchPlanningGraph,
)
from apps.api.src.modules.agents.infrastructure.search_adapters.tavily_search_executor import (
    TavilySearchExecutor,
)


def test_factory_returns_none_without_gemini_key(monkeypatch) -> None:
    monkeypatch.setattr(
        factory_module,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="",
            gemini_model="gemini-test",
            tavily_api_key="",
            tavily_search_url="https://api.tavily.com/search",
        ),
    )

    assert factory_module.AgentsFactory.create_evidence_validation_service() is None
    assert factory_module.AgentsFactory.create_search_planning_service() is None
    assert factory_module.AgentsFactory.create_search_executor() is None


def test_factory_creates_agent_graphs_when_gemini_key_exists(monkeypatch) -> None:
    monkeypatch.setattr(
        factory_module,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="secret",
            gemini_model="gemini-test",
            tavily_api_key="tavily-secret",
            tavily_search_url="https://api.tavily.com/search",
        ),
    )

    evidence_service = factory_module.AgentsFactory.create_evidence_validation_service()
    search_service = factory_module.AgentsFactory.create_search_planning_service()

    assert isinstance(evidence_service, EvidenceValidationGraph)
    assert evidence_service.model == "gemini-test"
    assert isinstance(search_service, SearchPlanningGraph)
    assert search_service.model == "gemini-test"
    assert isinstance(factory_module.AgentsFactory.create_search_executor(), TavilySearchExecutor)
