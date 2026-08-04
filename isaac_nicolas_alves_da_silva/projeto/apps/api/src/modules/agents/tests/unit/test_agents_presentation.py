"""Testes da presentation layer do modulo agents (V7)."""

from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from apps.api.src.modules.agents.application.dto import AgentRunView
from apps.api.src.modules.agents.domain.enums import AgentRunStatus, AgentType
from apps.api.src.modules.agents.presentation.schemas import AgentRunResponse


# ---------------------------------------------------------------------------
# Testes de schema
# ---------------------------------------------------------------------------


def test_agent_run_response_from_view_maps_fields() -> None:
    view = AgentRunView(
        id=uuid4(),
        agent_type=AgentType.EVIDENCE_VALIDATION,
        status=AgentRunStatus.COMPLETED,
        input_payload={"url": "https://x.com"},
        output_payload={"decision": "accepted"},
        error_message=None,
    )
    response = AgentRunResponse.from_view(view)

    assert response.agent_type == "evidence_validation"
    assert response.status == "completed"
    assert response.interrupt_value is None


def test_agent_run_response_extracts_interrupt_value_when_waiting() -> None:
    view = AgentRunView(
        id=uuid4(),
        agent_type=AgentType.EVIDENCE_VALIDATION,
        status=AgentRunStatus.WAITING_HUMAN_REVIEW,
        input_payload={"url": "https://x.com"},
        output_payload={"interrupt_value": "Approve or reject?"},
        error_message=None,
    )
    response = AgentRunResponse.from_view(view)

    assert response.status == "waiting_human_review"
    assert response.interrupt_value == "Approve or reject?"
    assert response.output_payload == {"interrupt_value": "Approve or reject?"}


def test_agent_run_response_interrupt_value_none_when_no_output() -> None:
    view = AgentRunView(
        id=uuid4(),
        agent_type=AgentType.EVIDENCE_VALIDATION,
        status=AgentRunStatus.RUNNING,
        input_payload={},
        output_payload=None,
        error_message=None,
    )
    response = AgentRunResponse.from_view(view)

    assert response.interrupt_value is None


# ---------------------------------------------------------------------------
# Testes do interrupt real no grafo
# ---------------------------------------------------------------------------


class FakeCheckpointer:
    """Checkpointer em memoria para testes de interrupt (nao precisa de PostgreSQL)."""

    def __init__(self) -> None:
        from langgraph.checkpoint.memory import MemorySaver

        self._saver = MemorySaver()

    async def get_saver(self):
        return self._saver


@pytest.mark.anyio
async def test_finalize_calls_interrupt_when_needs_more_sources_and_checkpointer_present() -> None:
    """Com checkpointer e interrupt_on_uncertain=True, NEEDS_MORE_SOURCES pausa o grafo."""

    from apps.api.src.modules.agents.application.dto import (
        EvidenceValidationInput,
        EvidenceValidationResult,
    )
    from apps.api.src.modules.agents.application.public.semantic_investigator import (
        EvidenceValidationService,
    )
    from apps.api.src.modules.agents.domain.enums import AgentDecision
    from apps.api.src.modules.agents.domain.exceptions import AgentRunInterruptedError
    from apps.api.src.modules.agents.graphs.evidence_validation.graph import (
        EvidenceValidationGraph,
    )

    class NeedsMoreSourcesJudge(EvidenceValidationService):
        async def investigate(self, inv_input, *, thread_id=None):
            return EvidenceValidationResult(
                decision=AgentDecision.NEEDS_MORE_SOURCES,
                reason="Evidencia fraca, mais fontes necessarias.",
            )

    graph = EvidenceValidationGraph(
        evidence_judge=NeedsMoreSourcesJudge(),
        checkpointer=FakeCheckpointer(),
        interrupt_on_uncertain=True,
    )

    investigation_input = EvidenceValidationInput(
        url="https://x.com",
        title="Test",
        raw_text="We use AI.",
        technical_score=0.8,
        text_score=0.7,
        evidence_score=0.5,
        quality_score=0.65,
    )

    with pytest.raises(AgentRunInterruptedError):
        await graph.investigate(investigation_input, thread_id="test-interrupt-1")


@pytest.mark.anyio
async def test_finalize_no_interrupt_without_checkpointer() -> None:
    """Sem checkpointer, NEEDS_MORE_SOURCES e retornado mesmo com interrupt_on_uncertain=True."""

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

    class NeedsMoreSourcesJudge(EvidenceValidationService):
        async def investigate(self, inv_input, *, thread_id=None):
            return EvidenceValidationResult(
                decision=AgentDecision.NEEDS_MORE_SOURCES,
                reason="Evidencia fraca.",
            )

    graph = EvidenceValidationGraph(
        evidence_judge=NeedsMoreSourcesJudge(),
        checkpointer=None,
        interrupt_on_uncertain=True,
    )

    investigation_input = EvidenceValidationInput(
        url="https://x.com",
        title="Test",
        raw_text="We use AI.",
        technical_score=0.8,
        text_score=0.7,
        evidence_score=0.5,
        quality_score=0.65,
    )

    result = await graph.investigate(investigation_input)
    assert result.decision is AgentDecision.NEEDS_MORE_SOURCES


@pytest.mark.anyio
async def test_finalize_does_not_interrupt_when_flag_false() -> None:
    """Com interrupt_on_uncertain=False, NEEDS_MORE_SOURCES e retornado normalmente."""

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

    class NeedsMoreSourcesJudge(EvidenceValidationService):
        async def investigate(self, inv_input, *, thread_id=None):
            return EvidenceValidationResult(
                decision=AgentDecision.NEEDS_MORE_SOURCES,
                reason="Evidencia fraca.",
            )

    graph = EvidenceValidationGraph(
        evidence_judge=NeedsMoreSourcesJudge(),
        interrupt_on_uncertain=False,
    )

    investigation_input = EvidenceValidationInput(
        url="https://x.com",
        title="Test",
        raw_text="We use AI.",
        technical_score=0.8,
        text_score=0.7,
        evidence_score=0.5,
        quality_score=0.65,
    )

    result = await graph.investigate(investigation_input)
    assert result.decision is AgentDecision.NEEDS_MORE_SOURCES


@pytest.mark.anyio
async def test_finalize_does_not_interrupt_for_accepted_decision() -> None:
    """ACCEPTED nunca causa interrupt, mesmo com interrupt_on_uncertain=True."""

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

    class AcceptingJudge(EvidenceValidationService):
        async def investigate(self, inv_input, *, thread_id=None):
            return EvidenceValidationResult(
                decision=AgentDecision.ACCEPTED,
                reason="Evidencia clara.",
            )

    graph = EvidenceValidationGraph(
        evidence_judge=AcceptingJudge(),
        interrupt_on_uncertain=True,
    )

    investigation_input = EvidenceValidationInput(
        url="https://x.com",
        title="Test",
        raw_text="We use AI.",
        technical_score=0.9,
        text_score=0.9,
        evidence_score=0.9,
        quality_score=0.9,
    )

    result = await graph.investigate(investigation_input)
    assert result.decision is AgentDecision.ACCEPTED
