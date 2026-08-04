"""Grafo LangGraph do Extraction Agent (V8)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, StateGraph

from apps.api.src.modules.agents.application.dto import (
    ExtractionInput,
    ExtractionResult,
)
from apps.api.src.modules.agents.application.public.extractor import (
    ExtractionService,
)
from apps.api.src.modules.agents.domain.exceptions import AgentRunInterruptedError
from apps.api.src.modules.agents.graphs.extraction.state import ExtractionState

if TYPE_CHECKING:
    from apps.api.src.modules.agents.infrastructure.checkpoints.postgres_checkpointer import (
        PostgresCheckpointer,
    )


class ExtractionGraph(ExtractionService):
    """Orquestra a extracao de dados estruturados usando LangGraph."""

    def __init__(
        self,
        *,
        extractor: ExtractionService,
        checkpointer: "PostgresCheckpointer | None" = None,
    ) -> None:
        self.extractor = extractor
        self.model = getattr(extractor, "model", None)
        self._checkpointer = checkpointer
        self._workflow = self._build_workflow()
        self._graph_no_cp = self._workflow.compile()
        self._graph_with_cp: Any = None

    async def extract(
        self,
        extraction_input: ExtractionInput,
        *,
        thread_id: str | None = None,
    ) -> ExtractionResult:
        """Executa o grafo e devolve os dados extraidos publicos."""

        graph, config = await self._resolve_graph_and_config(thread_id)
        final_state = await graph.ainvoke(
            {"extraction_input": extraction_input},
            config=config,
        )
        return self._extract_result(final_state)

    async def resume(
        self,
        thread_id: str,
        resume_value: object,
    ) -> ExtractionResult:
        """Retoma uma extracao pausada a partir do checkpoint salvo."""

        from langgraph.types import Command

        graph, config = await self._resolve_graph_and_config(thread_id)
        final_state = await graph.ainvoke(Command(resume=resume_value), config=config)
        return self._extract_result(final_state)

    def _extract_result(self, final_state: dict) -> ExtractionResult:
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
        workflow = StateGraph(ExtractionState)

        workflow.add_node("prepare_context", self._prepare_context)
        workflow.add_node("extract_data", self._extract_data)
        workflow.add_node("finalize", self._finalize)

        workflow.set_entry_point("prepare_context")
        workflow.add_edge("prepare_context", "extract_data")
        workflow.add_edge("extract_data", "finalize")
        workflow.add_edge("finalize", END)

        return workflow

    # NODES
    async def _prepare_context(self, state: ExtractionState) -> ExtractionState:
        extraction_input = state["extraction_input"]
        prepared_context = (
            f"name={extraction_input.name}; "
            f"sector={extraction_input.sector or 'unknown'}; "
            f"evidence_count={len(extraction_input.evidence_texts)}"
        )
        return {"prepared_context": prepared_context}

    async def _extract_data(self, state: ExtractionState) -> ExtractionState:
        result = await self.extractor.extract(state["extraction_input"])
        return {"llm_result": result}

    async def _finalize(self, state: ExtractionState) -> ExtractionState:
        return {"result": state["llm_result"]}
