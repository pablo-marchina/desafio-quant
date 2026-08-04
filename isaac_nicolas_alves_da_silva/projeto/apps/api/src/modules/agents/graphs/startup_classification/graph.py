"""Grafo LangGraph do Startup Classifier Agent (V9)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, StateGraph

from apps.api.src.modules.agents.application.dto import (
    StartupClassificationInput,
    StartupClassificationResult,
)
from apps.api.src.modules.agents.application.public.startup_classifier import (
    StartupClassifierService,
)
from apps.api.src.modules.agents.domain.exceptions import AgentRunInterruptedError
from apps.api.src.modules.agents.graphs.startup_classification.state import (
    StartupClassificationState,
)

if TYPE_CHECKING:
    from apps.api.src.modules.agents.infrastructure.checkpoints.postgres_checkpointer import (
        PostgresCheckpointer,
    )


class StartupClassificationGraph(StartupClassifierService):
    """Orquestra a classificacao de maturidade de IA usando LangGraph."""

    def __init__(
        self,
        *,
        classifier: StartupClassifierService,
        checkpointer: "PostgresCheckpointer | None" = None,
    ) -> None:
        self.classifier = classifier
        self.model = getattr(classifier, "model", None)
        self._checkpointer = checkpointer
        self._workflow = self._build_workflow()
        self._graph_no_cp = self._workflow.compile()
        self._graph_with_cp: Any = None

    async def classify(
        self,
        classification_input: StartupClassificationInput,
        *,
        thread_id: str | None = None,
    ) -> StartupClassificationResult:
        """Executa o grafo e devolve a classificacao publica."""

        graph, config = await self._resolve_graph_and_config(thread_id)
        final_state = await graph.ainvoke(
            {"classification_input": classification_input},
            config=config,
        )
        return self._extract_result(final_state)

    async def resume(
        self,
        thread_id: str,
        resume_value: object,
    ) -> StartupClassificationResult:
        """Retoma uma classificacao pausada a partir do checkpoint salvo."""

        from langgraph.types import Command

        graph, config = await self._resolve_graph_and_config(thread_id)
        final_state = await graph.ainvoke(Command(resume=resume_value), config=config)
        return self._extract_result(final_state)

    def _extract_result(self, final_state: dict) -> StartupClassificationResult:
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
        workflow = StateGraph(StartupClassificationState)

        workflow.add_node("prepare_context", self._prepare_context)
        workflow.add_node("classify_startup", self._classify_startup)
        workflow.add_node("finalize", self._finalize)

        workflow.set_entry_point("prepare_context")
        workflow.add_edge("prepare_context", "classify_startup")
        workflow.add_edge("classify_startup", "finalize")
        workflow.add_edge("finalize", END)

        return workflow

    # NODES
    async def _prepare_context(
        self,
        state: StartupClassificationState,
    ) -> StartupClassificationState:
        classification_input = state["classification_input"]
        prepared_context = (
            f"name={classification_input.name}; "
            f"sector={classification_input.sector or 'unknown'}; "
            f"evidence_count={len(classification_input.evidence_texts)}"
        )
        return {"prepared_context": prepared_context}

    async def _classify_startup(
        self,
        state: StartupClassificationState,
    ) -> StartupClassificationState:
        result = await self.classifier.classify(state["classification_input"])
        return {"llm_result": result}

    async def _finalize(
        self,
        state: StartupClassificationState,
    ) -> StartupClassificationState:
        return {"result": state["llm_result"]}
