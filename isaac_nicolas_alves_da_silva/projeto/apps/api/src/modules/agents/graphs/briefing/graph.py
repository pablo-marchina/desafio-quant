"""Grafo LangGraph do Briefing Agent (V12)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, StateGraph

from apps.api.src.modules.agents.application.dto import (
    BriefingAgentInput,
    BriefingAgentResult,
)
from apps.api.src.modules.agents.application.ports import (
    BriefingProseRewriterPort,
    BriefingToolPort,
)
from apps.api.src.modules.agents.application.public.briefing_agent import (
    BriefingAgentService,
)
from apps.api.src.modules.agents.domain.exceptions import AgentRunInterruptedError
from apps.api.src.modules.agents.graphs.briefing.state import BriefingState

if TYPE_CHECKING:
    from apps.api.src.modules.agents.infrastructure.checkpoints.postgres_checkpointer import (
        PostgresCheckpointer,
    )


class BriefingAgentGraph(BriefingAgentService):
    """Orquestra a geracao e reescrita do briefing executivo usando LangGraph.

    O node ``generate_briefing`` chama ``briefing`` (atraves de
    ``BriefingToolPort``) como tool, sem reimplementar
    ``build_briefing_markdown()``. O node ``rewrite_prose`` sempre aciona o
    LLM (reescrever a prosa e' o proposito inteiro deste agente, diferente
    do Recommendation Agent, que so aciona LLM para candidatos ambiguos) —
    o fallback seguro contra perda de citacoes fica dentro do
    ``BriefingProseRewriterPort``, nao aqui. O node ``persist_rewritten_content``
    grava a prosa reescrita de volta em ``briefing`` (sem isso, a reescrita
    nunca chegaria ao usuario — ficaria so na resposta em memoria deste
    grafo).
    """

    def __init__(
        self,
        *,
        briefing_tool: BriefingToolPort,
        prose_rewriter: BriefingProseRewriterPort,
        checkpointer: "PostgresCheckpointer | None" = None,
    ) -> None:
        self.briefing_tool = briefing_tool
        self.prose_rewriter = prose_rewriter
        self.model = getattr(prose_rewriter, "model", None)
        self._checkpointer = checkpointer
        self._workflow = self._build_workflow()
        self._graph_no_cp = self._workflow.compile()
        self._graph_with_cp: Any = None

    async def generate(
        self,
        briefing_input: BriefingAgentInput,
        *,
        thread_id: str | None = None,
    ) -> BriefingAgentResult:
        """Executa o grafo e devolve o briefing com prosa revisada."""

        graph, config = await self._resolve_graph_and_config(thread_id)
        final_state = await graph.ainvoke(
            {"briefing_input": briefing_input},
            config=config,
        )
        return self._extract_result(final_state)

    async def resume(
        self,
        thread_id: str,
        resume_value: object,
    ) -> BriefingAgentResult:
        """Retoma um briefing pausado a partir do checkpoint salvo."""

        from langgraph.types import Command

        graph, config = await self._resolve_graph_and_config(thread_id)
        final_state = await graph.ainvoke(Command(resume=resume_value), config=config)
        return self._extract_result(final_state)

    def _extract_result(self, final_state: dict) -> BriefingAgentResult:
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
        workflow = StateGraph(BriefingState)

        workflow.add_node("prepare_context", self._prepare_context)
        workflow.add_node("generate_briefing", self._generate_briefing)
        workflow.add_node("rewrite_prose", self._rewrite_prose)
        workflow.add_node(
            "persist_rewritten_content", self._persist_rewritten_content
        )
        workflow.add_node("finalize", self._finalize)

        workflow.set_entry_point("prepare_context")
        workflow.add_edge("prepare_context", "generate_briefing")
        workflow.add_edge("generate_briefing", "rewrite_prose")
        workflow.add_edge("rewrite_prose", "persist_rewritten_content")
        workflow.add_edge("persist_rewritten_content", "finalize")
        workflow.add_edge("finalize", END)

        return workflow

    # NODES
    async def _prepare_context(self, state: BriefingState) -> BriefingState:
        briefing_input = state["briefing_input"]
        prepared_context = f"startup_id={briefing_input.startup_id}"
        return {"prepared_context": prepared_context}

    async def _generate_briefing(self, state: BriefingState) -> BriefingState:
        briefing_input = state["briefing_input"]
        content = await self.briefing_tool.generate(briefing_input.startup_id)
        return {"deterministic_content": content}

    async def _rewrite_prose(self, state: BriefingState) -> BriefingState:
        content = state["deterministic_content"]
        rewritten = await self.prose_rewriter.rewrite(content)
        return {"rewritten_content": rewritten}

    async def _persist_rewritten_content(self, state: BriefingState) -> BriefingState:
        startup_id = state["briefing_input"].startup_id
        briefing_id = await self.briefing_tool.update_content(
            startup_id, state["rewritten_content"]
        )
        return {"briefing_id": briefing_id}

    async def _finalize(self, state: BriefingState) -> BriefingState:
        return {
            "result": BriefingAgentResult(
                content=state["rewritten_content"],
                briefing_id=state["briefing_id"],
            )
        }
