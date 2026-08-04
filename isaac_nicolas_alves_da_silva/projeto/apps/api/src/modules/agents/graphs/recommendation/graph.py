"""Grafo LangGraph do Recommendation Agent (V11)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, StateGraph

from apps.api.src.modules.agents.application.dto import (
    RecommendationAgentInput,
    RecommendationAgentResult,
)
from apps.api.src.modules.agents.application.ports import (
    RecommendationReviewerPort,
    RecommendationToolPort,
)
from apps.api.src.modules.agents.application.public.recommendation_agent import (
    RecommendationAgentService,
)
from apps.api.src.modules.agents.domain.exceptions import AgentRunInterruptedError
from apps.api.src.modules.agents.graphs.recommendation.state import (
    RecommendationState,
)

if TYPE_CHECKING:
    from apps.api.src.modules.agents.infrastructure.checkpoints.postgres_checkpointer import (
        PostgresCheckpointer,
    )


class RecommendationAgentGraph(RecommendationAgentService):
    """Orquestra a geracao e revisao de recomendacoes usando LangGraph.

    O node ``generate_recommendations`` chama ``recommendations`` (atraves
    de ``RecommendationToolPort``) como tool, sem reimplementar
    ``match_technologies()``. O node ``review_and_enrich`` so aciona o LLM
    quando ha pelo menos um candidato — recomendacoes vazias nao custam
    chamada nenhuma. O node ``persist_reviewed_candidates`` grava a
    justificativa revisada de volta em ``recommendations`` (sem isso, a
    melhoria do LLM nunca chegaria ao usuario — ficaria so na resposta em
    memoria deste grafo).
    """

    def __init__(
        self,
        *,
        recommendation_tool: RecommendationToolPort,
        reviewer: RecommendationReviewerPort,
        checkpointer: "PostgresCheckpointer | None" = None,
    ) -> None:
        self.recommendation_tool = recommendation_tool
        self.reviewer = reviewer
        self.model = getattr(reviewer, "model", None)
        self._checkpointer = checkpointer
        self._workflow = self._build_workflow()
        self._graph_no_cp = self._workflow.compile()
        self._graph_with_cp: Any = None

    async def recommend(
        self,
        recommendation_input: RecommendationAgentInput,
        *,
        thread_id: str | None = None,
    ) -> RecommendationAgentResult:
        """Executa o grafo e devolve as recomendacoes revisadas."""

        graph, config = await self._resolve_graph_and_config(thread_id)
        final_state = await graph.ainvoke(
            {"recommendation_input": recommendation_input},
            config=config,
        )
        return self._extract_result(final_state)

    async def resume(
        self,
        thread_id: str,
        resume_value: object,
    ) -> RecommendationAgentResult:
        """Retoma uma recomendacao pausada a partir do checkpoint salvo."""

        from langgraph.types import Command

        graph, config = await self._resolve_graph_and_config(thread_id)
        final_state = await graph.ainvoke(Command(resume=resume_value), config=config)
        return self._extract_result(final_state)

    def _extract_result(self, final_state: dict) -> RecommendationAgentResult:
        if "__interrupt__" in final_state:
            interrupts = final_state["__interrupt__"]
            interrupt_value = repr(interrupts[0].value) if interrupts else "interrupt"
            raise AgentRunInterruptedError(interrupt_value)
        return final_state["result"]

    async def _resolve_graph_and_config(
        self, thread_id: str | None
    ) -> tuple[Any, dict]:
        if thread_id and self._checkpointer is not None:
            if self._graph_with_cp is None:
                saver = await self._checkpointer.get_saver()
                self._graph_with_cp = self._workflow.compile(checkpointer=saver)
            return self._graph_with_cp, {"configurable": {"thread_id": thread_id}}
        return self._graph_no_cp, {}

    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(RecommendationState)

        workflow.add_node("prepare_context", self._prepare_context)
        workflow.add_node("generate_recommendations", self._generate_recommendations)
        workflow.add_node("review_and_enrich", self._review_and_enrich)
        workflow.add_node(
            "persist_reviewed_candidates", self._persist_reviewed_candidates
        )
        workflow.add_node("finalize", self._finalize)

        workflow.set_entry_point("prepare_context")
        workflow.add_edge("prepare_context", "generate_recommendations")
        workflow.add_edge("generate_recommendations", "review_and_enrich")
        workflow.add_edge("review_and_enrich", "persist_reviewed_candidates")
        workflow.add_edge("persist_reviewed_candidates", "finalize")
        workflow.add_edge("finalize", END)

        return workflow

    # NODES
    async def _prepare_context(self, state: RecommendationState) -> RecommendationState:
        recommendation_input = state["recommendation_input"]
        prepared_context = f"startup_id={recommendation_input.startup_id}"
        return {"prepared_context": prepared_context}

    async def _generate_recommendations(
        self, state: RecommendationState
    ) -> RecommendationState:
        recommendation_input = state["recommendation_input"]
        candidates = await self.recommendation_tool.generate(
            recommendation_input.startup_id
        )
        return {"candidates": candidates}

    async def _review_and_enrich(self, state: RecommendationState) -> RecommendationState:
        candidates = state["candidates"]
        if not candidates:
            return {"reviewed_candidates": []}

        reviewed = await self.reviewer.review(candidates)
        return {"reviewed_candidates": reviewed}

    async def _persist_reviewed_candidates(
        self, state: RecommendationState
    ) -> RecommendationState:
        reviewed = state["reviewed_candidates"]
        if reviewed:
            startup_id = state["recommendation_input"].startup_id
            justifications = {
                candidate.technology_slug: candidate.justification
                for candidate in reviewed
            }
            await self.recommendation_tool.update_justifications(
                startup_id, justifications
            )
        return {}

    async def _finalize(self, state: RecommendationState) -> RecommendationState:
        return {
            "result": RecommendationAgentResult(
                recommendations=state["reviewed_candidates"]
            )
        }
