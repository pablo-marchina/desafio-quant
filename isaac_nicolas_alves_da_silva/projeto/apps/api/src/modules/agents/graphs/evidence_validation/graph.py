"""Grafo LangGraph do Evidence Validation Agent (V7: interrupt real em node).

A V7 ativa ``interrupt()`` real no node ``_finalize`` quando a decisao e
``NEEDS_MORE_SOURCES`` e o grafo tem checkpointer. LangGraph retorna
``__interrupt__`` no estado final (nao lanca excecao); o grafo converte isso
em ``AgentRunInterruptedError`` para a camada de aplicacao.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from apps.api.src.modules.agents.application.dto import (
    EvidenceValidationInput,
    EvidenceValidationResult,
)
from apps.api.src.modules.agents.application.public.semantic_investigator import (
    EvidenceValidationService,
)
from apps.api.src.modules.agents.domain.enums import AgentDecision
from apps.api.src.modules.agents.domain.exceptions import AgentRunInterruptedError
from apps.api.src.modules.agents.graphs.evidence_validation.state import (
    EvidenceValidationState,
)

if TYPE_CHECKING:
    from apps.api.src.modules.agents.infrastructure.checkpoints.postgres_checkpointer import (
        PostgresCheckpointer,
    )


class EvidenceValidationGraph(EvidenceValidationService):
    """Orquestra a validacao de evidencia usando LangGraph.

    Quando ``interrupt_on_uncertain=True`` e um checkpointer esta presente,
    o node ``_finalize`` chama ``interrupt()`` ao receber ``NEEDS_MORE_SOURCES``.
    ``ainvoke()`` retorna o estado com ``__interrupt__`` em vez de levantar
    excecao. O metodo ``investigate()`` converte isso em ``AgentRunInterruptedError``.
    """

    def __init__(
        self,
        *,
        evidence_judge: EvidenceValidationService,
        checkpointer: "PostgresCheckpointer | None" = None,
        interrupt_on_uncertain: bool = False,
    ) -> None:
        self.evidence_judge = evidence_judge
        self.model = getattr(evidence_judge, "model", None)
        self._checkpointer = checkpointer
        self._interrupt_on_uncertain = interrupt_on_uncertain
        self._workflow = self._build_workflow()
        self._graph_no_cp = self._workflow.compile()
        self._graph_with_cp: Any = None

    async def investigate(
        self,
        investigation_input: EvidenceValidationInput,
        *,
        thread_id: str | None = None,
    ) -> EvidenceValidationResult:
        """Executa o grafo e devolve apenas o resultado publico.

        Se o grafo retornar ``__interrupt__``, converte em ``AgentRunInterruptedError``.
        """

        graph, config = await self._resolve_graph_and_config(thread_id)
        final_state = await graph.ainvoke(
            {"investigation_input": investigation_input},
            config=config,
        )
        return self._extract_result(final_state)

    async def resume(
        self,
        thread_id: str,
        resume_value: object,
    ) -> EvidenceValidationResult:
        """Retoma uma investigacao pausada a partir do checkpoint salvo."""

        from langgraph.types import Command

        graph, config = await self._resolve_graph_and_config(thread_id)
        final_state = await graph.ainvoke(Command(resume=resume_value), config=config)
        return self._extract_result(final_state)

    def _extract_result(self, final_state: dict) -> EvidenceValidationResult:
        """Extrai resultado ou lanca AgentRunInterruptedError se o grafo pausou."""

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
        workflow = StateGraph(EvidenceValidationState)

        workflow.add_node("prepare_context", self._prepare_context)
        workflow.add_node("judge_evidence", self._judge_evidence)
        workflow.add_node("finalize", self._finalize)

        workflow.set_entry_point("prepare_context")
        workflow.add_edge("prepare_context", "judge_evidence")
        workflow.add_edge("judge_evidence", "finalize")
        workflow.add_edge("finalize", END)

        return workflow

    async def _prepare_context(
        self,
        state: EvidenceValidationState,
    ) -> EvidenceValidationState:
        investigation_input = state["investigation_input"]
        prepared_context = (
            f"url={investigation_input.url}; "
            f"quality_score={investigation_input.quality_score}; "
            f"semantic_confidence={investigation_input.semantic_confidence}; "
            f"semantic_decision={investigation_input.semantic_decision}"
        )
        return {"prepared_context": prepared_context}

    async def _judge_evidence(
        self,
        state: EvidenceValidationState,
    ) -> EvidenceValidationState:
        result = await self.evidence_judge.investigate(state["investigation_input"])
        return {"llm_result": result}

    async def _finalize(
        self,
        state: EvidenceValidationState,
    ) -> EvidenceValidationState:
        """Normaliza a saida final.

        Chama ``interrupt()`` quando a decisao e inconclusiva e o grafo tem
        checkpointer. Apos retomada, ``interrupt()`` retorna a decisao humana.
        """

        result = state["llm_result"]

        if (
            self._interrupt_on_uncertain
            and self._checkpointer is not None
            and result.decision is AgentDecision.NEEDS_MORE_SOURCES
        ):
            human_decision = interrupt(
                {
                    "original_decision": result.decision.value,
                    "reason": result.reason,
                    "question": "Evidencia inconclusiva. Responda 'approved' para aceitar ou 'rejected' para rejeitar.",
                }
            )
            accepted = str(human_decision).lower() in ("approved", "approve", "yes", "sim")
            result = EvidenceValidationResult(
                decision=AgentDecision.ACCEPTED if accepted else AgentDecision.REJECTED,
                reason=f"Decisao humana: '{human_decision}'. Razao original: {result.reason}",
            )

        return {"result": result}
