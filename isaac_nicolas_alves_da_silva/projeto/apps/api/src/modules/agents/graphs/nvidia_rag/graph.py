"""Grafo LangGraph do NVIDIA RAG Agent (V10)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, StateGraph

from apps.api.src.modules.agents.application.dto import (
    NvidiaRagInput,
    NvidiaRagResult,
)
from apps.api.src.modules.agents.application.ports import NvidiaRagToolPort
from apps.api.src.modules.agents.application.public.nvidia_rag import (
    NvidiaRagService,
)
from apps.api.src.modules.agents.domain.exceptions import AgentRunInterruptedError
from apps.api.src.modules.agents.graphs.nvidia_rag.state import NvidiaRagState

if TYPE_CHECKING:
    from apps.api.src.modules.agents.infrastructure.checkpoints.postgres_checkpointer import (
        PostgresCheckpointer,
    )


class NvidiaRagGraph(NvidiaRagService):
    """Orquestra a consulta a base NVIDIA via RAG usando LangGraph.

    Grafo fino: o node ``query_rag`` chama ``rag`` (atraves de
    ``NvidiaRagToolPort``) como tool, sem reimplementar busca hibrida,
    reranking ou geracao de resposta — toda essa logica ja existe em
    ``rag`` V4.
    """

    def __init__(
        self,
        *,
        rag_tool: NvidiaRagToolPort,
        checkpointer: "PostgresCheckpointer | None" = None,
    ) -> None:
        self.rag_tool = rag_tool
        self.model = getattr(rag_tool, "model", None)
        self._checkpointer = checkpointer
        self._workflow = self._build_workflow()
        self._graph_no_cp = self._workflow.compile()
        self._graph_with_cp: Any = None

    async def answer(
        self,
        rag_input: NvidiaRagInput,
        *,
        thread_id: str | None = None,
    ) -> NvidiaRagResult:
        """Executa o grafo e devolve a resposta publica."""

        graph, config = await self._resolve_graph_and_config(thread_id)
        final_state = await graph.ainvoke(
            {"rag_input": rag_input},
            config=config,
        )
        return self._extract_result(final_state)

    async def resume(
        self,
        thread_id: str,
        resume_value: object,
    ) -> NvidiaRagResult:
        """Retoma uma consulta pausada a partir do checkpoint salvo."""

        from langgraph.types import Command

        graph, config = await self._resolve_graph_and_config(thread_id)
        final_state = await graph.ainvoke(Command(resume=resume_value), config=config)
        return self._extract_result(final_state)

    def _extract_result(self, final_state: dict) -> NvidiaRagResult:
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
        workflow = StateGraph(NvidiaRagState)

        workflow.add_node("prepare_context", self._prepare_context)
        workflow.add_node("query_rag", self._query_rag)
        workflow.add_node("finalize", self._finalize)

        workflow.set_entry_point("prepare_context")
        workflow.add_edge("prepare_context", "query_rag")
        workflow.add_edge("query_rag", "finalize")
        workflow.add_edge("finalize", END)

        return workflow

    # NODES
    async def _prepare_context(self, state: NvidiaRagState) -> NvidiaRagState:
        rag_input = state["rag_input"]
        prepared_context = f"query={rag_input.query}; limit={rag_input.limit}"
        return {"prepared_context": prepared_context}

    async def _query_rag(self, state: NvidiaRagState) -> NvidiaRagState:
        rag_input = state["rag_input"]
        result = await self.rag_tool.answer(rag_input.query, limit=rag_input.limit)
        return {"llm_result": result}

    async def _finalize(self, state: NvidiaRagState) -> NvidiaRagState:
        return {"result": state["llm_result"]}
