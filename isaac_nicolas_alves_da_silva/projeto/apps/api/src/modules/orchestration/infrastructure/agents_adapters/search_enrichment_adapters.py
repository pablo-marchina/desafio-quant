"""Adaptadores de agents usados pela chain de enriquecimento da orquestracao."""

from apps.api.src.modules.agents.application.dto import SearchPlanInput
from apps.api.src.modules.agents.application.ports import (
    SearchExecutorPort as AgentsSearchExecutorPort,
)
from apps.api.src.modules.agents.application.public.search_planner import (
    SearchPlanningService,
)
from apps.api.src.modules.orchestration.application.ports import (
    EnrichmentSearchCandidate,
    EnrichmentSearchExecutorPort,
    EnrichmentSearchPlannerPort,
)


class AgentsSearchPlannerAdapter(EnrichmentSearchPlannerPort):
    """Traduz o contrato publico do Search Planner para orchestration."""

    def __init__(self, service: SearchPlanningService) -> None:
        self._service = service

    async def plan_queries(
        self,
        *,
        startup_name: str,
        source_url: str,
        source_title: str | None,
        raw_text: str,
        missing_signals: list[str],
        known_terms: list[str],
        excluded_urls: list[str],
        max_queries: int = 3,
    ) -> list[str]:
        result = await self._service.plan_searches(
            SearchPlanInput(
                startup_name=startup_name,
                source_url=source_url,
                source_title=source_title,
                raw_text=raw_text,
                reason=(
                    "Perfil incompleto apos extracao. Campos faltantes: "
                    + ", ".join(missing_signals)
                ),
                known_terms=known_terms,
                excluded_urls=excluded_urls,
                max_queries=max_queries,
            )
        )
        ordered = sorted(result.queries, key=lambda item: item.priority)
        return [item.query for item in ordered]


class AgentsSearchExecutorAdapter(EnrichmentSearchExecutorPort):
    """Traduz resultados do SearchExecutorPort de agents para orchestration."""

    def __init__(self, executor: AgentsSearchExecutorPort) -> None:
        self._executor = executor

    async def search(
        self,
        query: str,
        *,
        excluded_urls: list[str],
        max_results: int = 2,
    ) -> list[EnrichmentSearchCandidate]:
        result = await self._executor.search(
            query,
            excluded_urls=excluded_urls,
            max_results=max_results,
        )
        return [
            EnrichmentSearchCandidate(
                url=item.url,
                title=item.title,
                snippet=item.snippet,
            )
            for item in result.results
        ]
