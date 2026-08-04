"""Grafo LangGraph do Search Planner Agent (V7: padrao __interrupt__ consistente).

Usa o mesmo padrao de _extract_result do EvidenceValidationGraph:
``ainvoke()`` retorna ``__interrupt__`` no estado em vez de levantar excecao.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, StateGraph

from apps.api.src.modules.agents.application.dto import (
    SearchPlanInput,
    SearchPlanResult,
)
from apps.api.src.modules.agents.application.public.search_planner import (
    SearchPlanningService,
)
from apps.api.src.modules.agents.domain.exceptions import AgentRunInterruptedError
from apps.api.src.modules.agents.graphs.search_planning.state import (
    SearchPlanningState,
)

if TYPE_CHECKING:
    from apps.api.src.modules.agents.infrastructure.checkpoints.postgres_checkpointer import (
        PostgresCheckpointer,
    )


class SearchPlanningGraph(SearchPlanningService):
    """Orquestra a geracao de plano de busca usando LangGraph."""

    def __init__(
        self,
        *,
        planner: SearchPlanningService,
        checkpointer: "PostgresCheckpointer | None" = None,
    ) -> None:
        self.planner = planner
        self.model = getattr(planner, "model", None)
        self._checkpointer = checkpointer
        self._workflow = self._build_workflow()
        self._graph_no_cp = self._workflow.compile()
        self._graph_with_cp: Any = None

    async def plan_searches(
        self,
        plan_input: SearchPlanInput,
        *,
        thread_id: str | None = None,
    ) -> SearchPlanResult:
        """Executa o grafo e devolve o plano publico."""

        graph, config = await self._resolve_graph_and_config(thread_id)
        final_state = await graph.ainvoke({"plan_input": plan_input}, config=config)
        return self._extract_result(final_state)

    async def resume(
        self,
        thread_id: str,
        resume_value: object,
    ) -> SearchPlanResult:
        """Retoma um planejamento pausado a partir do checkpoint salvo."""

        from langgraph.types import Command

        graph, config = await self._resolve_graph_and_config(thread_id)
        final_state = await graph.ainvoke(Command(resume=resume_value), config=config)
        return self._extract_result(final_state)

    def _extract_result(self, final_state: dict) -> SearchPlanResult:
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
        workflow = StateGraph(SearchPlanningState)

        workflow.add_node("prepare_context", self._prepare_context)
        workflow.add_node("generate_plan", self._generate_plan)
        workflow.add_node("finalize", self._finalize)

        workflow.set_entry_point("prepare_context")
        workflow.add_edge("prepare_context", "generate_plan")
        workflow.add_edge("generate_plan", "finalize")
        workflow.add_edge("finalize", END)

        return workflow

    async def _prepare_context(
        self,
        state: SearchPlanningState,
    ) -> SearchPlanningState:
        plan_input = state["plan_input"]
        prepared_context = (
            f"startup={plan_input.startup_name or 'unknown'}; "
            f"source_url={plan_input.source_url}; "
            f"max_queries={plan_input.max_queries}; "
            f"known_terms={len(plan_input.known_terms)}"
        )
        return {"prepared_context": prepared_context}

    async def _generate_plan(
        self,
        state: SearchPlanningState,
    ) -> SearchPlanningState:
        plan = await self.planner.plan_searches(state["plan_input"])
        return {"llm_plan": plan}

    async def _finalize(
        self,
        state: SearchPlanningState,
    ) -> SearchPlanningState:
        return {"result": state["llm_plan"]}
