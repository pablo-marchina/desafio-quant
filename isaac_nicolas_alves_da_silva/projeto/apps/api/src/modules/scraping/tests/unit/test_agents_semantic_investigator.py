"""Testes do adaptador que liga o scraping ao contrato público de agents (v8)."""

import pytest

from apps.api.src.modules.agents.application.dto import (
    EvidenceValidationInput,
    EvidenceValidationResult,
)
from apps.api.src.modules.agents.application.public.semantic_investigator import (
    EvidenceValidationService,
)
from apps.api.src.modules.agents.domain.enums import AgentDecision
from apps.api.src.modules.scraping.application.dto import (
    DeterministicValidationResult,
    InvestigationInput,
    SemanticAssessment,
)
from apps.api.src.modules.scraping.application.semantic_confidence_service import (
    SemanticConfidenceService,
)
from apps.api.src.modules.scraping.domain.enums import (
    AgentInvestigationDecision,
    SemanticReviewDecision,
)
from apps.api.src.modules.scraping.infrastructure.agent_adapters.agents_semantic_investigator import (
    AgentsSemanticInvestigator,
)


class FakeEvidenceValidationService(EvidenceValidationService):
    """Captura a entrada recebida e devolve uma decisão configurável."""

    def __init__(self, decision: AgentDecision, reason: str) -> None:
        self.decision = decision
        self.reason = reason
        self.received_input: EvidenceValidationInput | None = None

    async def investigate(
        self, investigation_input: EvidenceValidationInput
    ) -> EvidenceValidationResult:
        self.received_input = investigation_input
        return EvidenceValidationResult(decision=self.decision, reason=self.reason)


def make_investigation_input() -> InvestigationInput:
    deterministic = DeterministicValidationResult(
        technical_score=0.90,
        text_score=0.80,
        evidence_score=0.20,
        quality_score=0.59,
        problems={"low_evidence"},
        warnings={"semantic_reviewed"},
    )
    assessment = SemanticAssessment(
        startup_match_score=0.70,
        evidence_clarity_score=0.60,
        source_reliability_score=0.50,
        statement_specificity_score=0.40,
        context_completeness_score=0.30,
        contradiction_detected=False,
        decision=SemanticReviewDecision.NEEDS_AGENT_REVIEW,
        reason="A revisão simples não teve confiança suficiente.",
    )
    semantic = SemanticConfidenceService().calculate(assessment)

    return InvestigationInput(
        url="https://example.com",
        title="Startup XYZ",
        raw_text="A Startup XYZ atua com IA generativa...",
        deterministic=deterministic,
        semantic=semantic,
    )


@pytest.mark.anyio
async def test_adapter_translates_input_fields() -> None:
    service = FakeEvidenceValidationService(
        decision=AgentDecision.ACCEPTED, reason="ok"
    )
    adapter = AgentsSemanticInvestigator(service)
    investigation_input = make_investigation_input()

    await adapter.investigate(investigation_input)

    sent = service.received_input
    assert sent is not None
    assert sent.url == investigation_input.url
    assert sent.title == investigation_input.title
    assert sent.raw_text == investigation_input.raw_text
    assert sent.technical_score == investigation_input.deterministic.technical_score
    assert sent.evidence_score == investigation_input.deterministic.evidence_score
    assert sent.deterministic_problems == ["low_evidence"]
    assert sent.deterministic_warnings == ["semantic_reviewed"]
    assert (
        sent.startup_match_score
        == investigation_input.semantic.assessment.startup_match_score
    )
    assert sent.semantic_decision == "needs_agent_review"
    assert sent.semantic_confidence == investigation_input.semantic.semantic_confidence


@pytest.mark.parametrize(
    ("agents_decision", "scraping_decision"),
    [
        (AgentDecision.ACCEPTED, AgentInvestigationDecision.ACCEPTED),
        (AgentDecision.REJECTED, AgentInvestigationDecision.REJECTED),
        (
            AgentDecision.NEEDS_MORE_SOURCES,
            AgentInvestigationDecision.NEEDS_MORE_SOURCES,
        ),
    ],
)
@pytest.mark.anyio
async def test_adapter_translates_decision_enum(
    agents_decision: AgentDecision,
    scraping_decision: AgentInvestigationDecision,
) -> None:
    service = FakeEvidenceValidationService(
        decision=agents_decision, reason="motivo qualquer"
    )
    adapter = AgentsSemanticInvestigator(service)

    result = await adapter.investigate(make_investigation_input())

    assert result.decision is scraping_decision
    assert result.reason == "motivo qualquer"
