"""Testes da V3 do Search Planner Agent com LangGraph."""

import pytest

from apps.api.src.modules.agents.application.dto import (
    SearchPlanInput,
    SearchPlanResult,
    SearchQuerySuggestion,
)
from apps.api.src.modules.agents.application.public.search_planner import (
    SearchPlanningService,
)
from apps.api.src.modules.agents.graphs.search_planning.graph import (
    SearchPlanningGraph,
)


class FakeSearchPlanner(SearchPlanningService):
    """Planejador falso para testar o grafo sem chamar LLM real."""

    def __init__(self, result: SearchPlanResult) -> None:
        self.result = result
        self.received_input: SearchPlanInput | None = None

    async def plan_searches(self, plan_input: SearchPlanInput) -> SearchPlanResult:
        self.received_input = plan_input
        return self.result


def make_input(**overrides) -> SearchPlanInput:
    defaults: dict = dict(
        startup_name="Startup Example",
        source_url="https://example.com",
        source_title="About Startup Example",
        raw_text="Texto insuficiente sobre produto e uso de IA.",
        reason="A evidencia atual nao confirma o uso de IA.",
        known_terms=["Startup Example", "AI"],
        max_queries=3,
    )
    defaults.update(overrides)
    return SearchPlanInput(**defaults)


@pytest.mark.anyio
async def test_graph_returns_search_plan() -> None:
    expected = SearchPlanResult(
        queries=[
            SearchQuerySuggestion(
                query="Startup Example official website",
                purpose="Encontrar fonte oficial.",
                priority=1,
            )
        ],
        reason="Buscar fonte oficial primeiro.",
    )
    fake_planner = FakeSearchPlanner(expected)
    graph = SearchPlanningGraph(planner=fake_planner)
    plan_input = make_input()

    result = await graph.plan_searches(plan_input)

    assert result == expected
    assert fake_planner.received_input == plan_input


@pytest.mark.anyio
async def test_graph_preserves_multiple_queries() -> None:
    expected = SearchPlanResult(
        queries=[
            SearchQuerySuggestion(
                query="Startup Example founders",
                purpose="Validar fundadores.",
                priority=2,
            ),
            SearchQuerySuggestion(
                query="Startup Example funding",
                purpose="Validar financiamento.",
                priority=3,
            ),
        ],
        reason="Coletar fontes complementares.",
    )
    graph = SearchPlanningGraph(planner=FakeSearchPlanner(expected))

    result = await graph.plan_searches(make_input())

    assert len(result.queries) == 2
    assert result.queries[0].query == "Startup Example founders"
    assert result.queries[1].priority == 3
