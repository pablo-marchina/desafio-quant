"""Testes das entidades AgentRun e AgentStep."""

import pytest

from apps.api.src.modules.agents.domain.entities import AgentRun, AgentStep
from apps.api.src.modules.agents.domain.enums import (
    AgentRunStatus,
    AgentStepStatus,
    AgentType,
)
from apps.api.src.modules.agents.domain.exceptions import (
    InvalidAgentRunTransitionError,
    InvalidAgentStepTransitionError,
)


def test_agent_run_lifecycle() -> None:
    run = AgentRun(
        agent_type=AgentType.EVIDENCE_VALIDATION,
        input_payload={"url": "https://example.com"},
    )

    run.start()
    run.complete({"decision": "accepted"})

    assert run.status is AgentRunStatus.COMPLETED
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.output_payload == {"decision": "accepted"}


def test_agent_run_rejects_invalid_start_transition() -> None:
    run = AgentRun(
        agent_type=AgentType.SEARCH_PLANNING,
        input_payload={},
    )
    run.start()

    with pytest.raises(InvalidAgentRunTransitionError):
        run.start()


def test_agent_step_lifecycle() -> None:
    run = AgentRun(agent_type=AgentType.SEARCH_PLANNING, input_payload={})
    step = AgentStep(run_id=run.id, name="generate_plan")

    step.complete({"queries": []})

    assert step.status is AgentStepStatus.COMPLETED
    assert step.finished_at is not None


def test_agent_step_rejects_invalid_completion_transition() -> None:
    run = AgentRun(agent_type=AgentType.SEARCH_PLANNING, input_payload={})
    step = AgentStep(run_id=run.id, name="generate_plan")
    step.complete({})

    with pytest.raises(InvalidAgentStepTransitionError):
        step.complete({})


# ---------------------------------------------------------------------------
# V6: interrupt / resume transitions
# ---------------------------------------------------------------------------


def test_agent_run_interrupt_transitions_to_waiting_human_review() -> None:
    run = AgentRun(
        agent_type=AgentType.EVIDENCE_VALIDATION,
        input_payload={"url": "https://example.com"},
    )
    run.start()
    run.interrupt("Decisao ambigua: approve or reject?")

    assert run.status is AgentRunStatus.WAITING_HUMAN_REVIEW
    assert run.output_payload is not None
    assert "interrupt_value" in run.output_payload
    assert run.finished_at is None


def test_agent_run_resume_transitions_back_to_running() -> None:
    run = AgentRun(
        agent_type=AgentType.EVIDENCE_VALIDATION,
        input_payload={"url": "https://example.com"},
    )
    run.start()
    run.interrupt("approve?")
    run.resume()

    assert run.status is AgentRunStatus.RUNNING
    assert run.output_payload is None


def test_agent_run_interrupt_rejects_non_running_run() -> None:
    run = AgentRun(
        agent_type=AgentType.EVIDENCE_VALIDATION,
        input_payload={},
    )
    with pytest.raises(InvalidAgentRunTransitionError):
        run.interrupt("should fail — run is still pending")


def test_agent_run_resume_rejects_non_waiting_run() -> None:
    run = AgentRun(
        agent_type=AgentType.EVIDENCE_VALIDATION,
        input_payload={},
    )
    run.start()
    with pytest.raises(InvalidAgentRunTransitionError):
        run.resume()


def test_agent_run_full_interrupt_resume_complete_lifecycle() -> None:
    run = AgentRun(
        agent_type=AgentType.EVIDENCE_VALIDATION,
        input_payload={"url": "https://example.com"},
    )
    run.start()
    run.interrupt("needs human approval")
    run.resume()
    run.complete({"decision": "accepted"})

    assert run.status is AgentRunStatus.COMPLETED
    assert run.output_payload == {"decision": "accepted"}
