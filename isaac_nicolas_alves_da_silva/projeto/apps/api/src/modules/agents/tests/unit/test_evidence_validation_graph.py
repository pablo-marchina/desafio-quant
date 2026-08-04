"""Testes da V2 do Evidence Validation Agent com LangGraph."""

import pytest

from apps.api.src.modules.agents.application.dto import (
    EvidenceValidationInput,
    EvidenceValidationResult,
)
from apps.api.src.modules.agents.application.public.semantic_investigator import (
    EvidenceValidationService,
)
from apps.api.src.modules.agents.domain.enums import AgentDecision
from apps.api.src.modules.agents.graphs.evidence_validation.graph import (
    EvidenceValidationGraph,
)


class FakeEvidenceJudge(EvidenceValidationService):
    """Avaliador falso usado para testar o grafo sem chamar LLM real."""

    def __init__(self, result: EvidenceValidationResult) -> None:
        self.result = result
        self.received_input: EvidenceValidationInput | None = None

    async def investigate(
        self,
        investigation_input: EvidenceValidationInput,
    ) -> EvidenceValidationResult:
        self.received_input = investigation_input
        return self.result


def make_input(**overrides) -> EvidenceValidationInput:
    """Cria uma entrada minima valida para o agente."""

    defaults: dict = dict(
        url="https://example.com/startup",
        title="Startup Example",
        raw_text="A Startup Example desenvolve IA para otimizar inferencia.",
        technical_score=0.90,
        text_score=0.85,
        evidence_score=0.45,
        quality_score=0.70,
        semantic_decision="needs_agent_review",
        semantic_reason="A evidencia parece relevante, mas ainda e fraca.",
        semantic_confidence=0.52,
    )
    defaults.update(overrides)
    return EvidenceValidationInput(**defaults)


@pytest.mark.anyio
async def test_graph_returns_judge_decision() -> None:
    expected = EvidenceValidationResult(
        decision=AgentDecision.ACCEPTED,
        reason="A pagina contem evidencia suficiente.",
    )
    judge = FakeEvidenceJudge(expected)
    graph = EvidenceValidationGraph(evidence_judge=judge)
    investigation_input = make_input()

    result = await graph.investigate(investigation_input)

    assert result == expected
    assert judge.received_input == investigation_input


@pytest.mark.anyio
async def test_graph_preserves_needs_more_sources_decision() -> None:
    expected = EvidenceValidationResult(
        decision=AgentDecision.NEEDS_MORE_SOURCES,
        reason="A pagina isolada nao basta para decidir.",
    )
    graph = EvidenceValidationGraph(evidence_judge=FakeEvidenceJudge(expected))

    result = await graph.investigate(make_input())

    assert result.decision is AgentDecision.NEEDS_MORE_SOURCES
    assert result.reason == "A pagina isolada nao basta para decidir."
