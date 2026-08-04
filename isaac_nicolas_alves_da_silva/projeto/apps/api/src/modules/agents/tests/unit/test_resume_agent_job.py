"""Testes do caso de uso ResumeAgentJob (Agents V6)."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.agents.application.dto import (
    EvidenceValidationInput,
    EvidenceValidationResult,
    SearchPlanInput,
    SearchPlanResult,
    SearchQuerySuggestion,
)
from apps.api.src.modules.agents.application.public.search_planner import (
    SearchPlanningService,
)
from apps.api.src.modules.agents.application.public.semantic_investigator import (
    EvidenceValidationService,
)
from apps.api.src.modules.agents.application.use_cases.resume_agent_job import (
    ResumeAgentJob,
)
from apps.api.src.modules.agents.domain.entities import AgentRun, AgentStep
from apps.api.src.modules.agents.domain.enums import (
    AgentDecision,
    AgentRunStatus,
    AgentStepStatus,
    AgentType,
)
from apps.api.src.modules.agents.domain.exceptions import (
    AgentRunInterruptedError,
    AgentRunNotFoundError,
    AgentServiceUnavailableError,
)

# ---------------------------------------------------------------------------
# Infra fakes reutilizaveis
# ---------------------------------------------------------------------------


class FakeRunRepository:
    def __init__(self, runs: dict[UUID, AgentRun]) -> None:
        self.runs = runs

    async def save(self, run: AgentRun) -> None:
        self.runs[run.id] = run

    async def get_by_id(self, run_id: UUID) -> AgentRun | None:
        return self.runs.get(run_id)


class FakeStepRepository:
    def __init__(self) -> None:
        self.steps: list[AgentStep] = []

    async def save(self, step: AgentStep) -> None:
        self.steps.append(step)

    async def list_by_run_id(self, run_id: UUID) -> list[AgentStep]:
        return [s for s in self.steps if s.run_id == run_id]


class FakeAgentsUnitOfWork:
    def __init__(self, runs: dict[UUID, AgentRun], steps: FakeStepRepository) -> None:
        self.run_repository = FakeRunRepository(runs)
        self.step_repository = steps

    async def __aenter__(self) -> "FakeAgentsUnitOfWork":
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def make_uow_factory(runs: dict[UUID, AgentRun], steps: FakeStepRepository):
    return lambda: FakeAgentsUnitOfWork(runs, steps)


# ---------------------------------------------------------------------------
# Servicos fake para resume
# ---------------------------------------------------------------------------


class ResumingEvidenceService(EvidenceValidationService):
    """Simula um grafo que retoma do checkpoint e completa."""

    async def investigate(
        self,
        investigation_input: EvidenceValidationInput,
        *,
        thread_id: str | None = None,
    ) -> EvidenceValidationResult:
        raise NotImplementedError("use resume()")

    async def resume(
        self, thread_id: str, resume_value: object
    ) -> EvidenceValidationResult:
        return EvidenceValidationResult(
            decision=AgentDecision.ACCEPTED,
            reason=f"Aprovado apos revisao: {resume_value}",
        )


class FailingResumeEvidenceService(EvidenceValidationService):
    async def investigate(
        self,
        investigation_input: EvidenceValidationInput,
        *,
        thread_id: str | None = None,
    ) -> EvidenceValidationResult:
        raise NotImplementedError

    async def resume(
        self, thread_id: str, resume_value: object
    ) -> EvidenceValidationResult:
        raise RuntimeError("LLM falhou no resume")


class DoubleInterruptEvidenceService(EvidenceValidationService):
    """Simula um grafo com dois pontos de interrupcao."""

    async def investigate(
        self,
        investigation_input: EvidenceValidationInput,
        *,
        thread_id: str | None = None,
    ) -> EvidenceValidationResult:
        raise NotImplementedError

    async def resume(
        self, thread_id: str, resume_value: object
    ) -> EvidenceValidationResult:
        raise AgentRunInterruptedError("segunda interrupcao: confirmar fonte?")


def _make_waiting_run(agent_type: AgentType = AgentType.EVIDENCE_VALIDATION) -> AgentRun:
    run = AgentRun(agent_type=agent_type, input_payload={"url": "https://x.com"})
    run.start()
    run.interrupt("approve?")
    return run


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_resume_evidence_validation_completes_run() -> None:
    run = _make_waiting_run(AgentType.EVIDENCE_VALIDATION)
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ResumeAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        evidence_validation_service=ResumingEvidenceService(),
    )
    await use_case.execute(run_id=run.id, resume_value="approved")

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.COMPLETED
    assert saved.output_payload is not None
    assert saved.output_payload["decision"] == AgentDecision.ACCEPTED.value
    assert "Aprovado apos revisao: approved" in saved.output_payload["reason"]


@pytest.mark.anyio
async def test_resume_creates_step_named_resume_agent_type() -> None:
    run = _make_waiting_run(AgentType.EVIDENCE_VALIDATION)
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ResumeAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        evidence_validation_service=ResumingEvidenceService(),
    )
    await use_case.execute(run_id=run.id, resume_value="ok")

    assert len(steps.steps) == 1
    step = steps.steps[0]
    assert step.name == "resume_evidence_validation"
    assert step.status is AgentStepStatus.COMPLETED
    assert step.input_payload is not None
    assert step.input_payload["resume_value"] == "ok"


@pytest.mark.anyio
async def test_resume_failure_marks_run_failed() -> None:
    run = _make_waiting_run(AgentType.EVIDENCE_VALIDATION)
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ResumeAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        evidence_validation_service=FailingResumeEvidenceService(),
    )
    await use_case.execute(run_id=run.id, resume_value="approved")

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.FAILED
    assert "LLM falhou no resume" in (saved.error_message or "")


@pytest.mark.anyio
async def test_resume_second_interrupt_keeps_waiting_human_review() -> None:
    run = _make_waiting_run(AgentType.EVIDENCE_VALIDATION)
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ResumeAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        evidence_validation_service=DoubleInterruptEvidenceService(),
    )
    await use_case.execute(run_id=run.id, resume_value="ok")

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.WAITING_HUMAN_REVIEW
    assert saved.output_payload is not None
    assert "segunda interrupcao" in saved.output_payload.get("interrupt_value", "")


@pytest.mark.anyio
async def test_resume_raises_when_run_not_found() -> None:
    use_case = ResumeAgentJob(uow_factory=make_uow_factory({}, FakeStepRepository()))

    with pytest.raises(AgentRunNotFoundError):
        await use_case.execute(run_id=uuid4(), resume_value="ok")


@pytest.mark.anyio
async def test_resume_raises_when_run_not_waiting() -> None:
    run = AgentRun(
        agent_type=AgentType.EVIDENCE_VALIDATION,
        input_payload={"url": "https://x.com"},
    )
    run.start()
    run.complete({"decision": "accepted"})
    runs = {run.id: run}

    use_case = ResumeAgentJob(
        uow_factory=make_uow_factory(runs, FakeStepRepository()),
        evidence_validation_service=ResumingEvidenceService(),
    )

    with pytest.raises(AgentRunNotFoundError):
        await use_case.execute(run_id=run.id, resume_value="ok")


@pytest.mark.anyio
async def test_resume_service_none_marks_run_failed() -> None:
    run = _make_waiting_run(AgentType.EVIDENCE_VALIDATION)
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ResumeAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        evidence_validation_service=None,
    )
    await use_case.execute(run_id=run.id, resume_value="ok")

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.FAILED
    assert "AgentServiceUnavailableError" in (saved.error_message or "")


@pytest.mark.anyio
async def test_resume_startup_classification_service_none_marks_run_failed() -> None:
    run = _make_waiting_run(AgentType.STARTUP_CLASSIFIER)
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ResumeAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        startup_classification_service=None,
    )
    await use_case.execute(run_id=run.id, resume_value="ok")

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.FAILED
    assert "AgentServiceUnavailableError" in (saved.error_message or "")


@pytest.mark.anyio
async def test_resume_extraction_service_none_marks_run_failed() -> None:
    run = _make_waiting_run(AgentType.EXTRACTION)
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ResumeAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        extraction_service=None,
    )
    await use_case.execute(run_id=run.id, resume_value="ok")

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.FAILED
    assert "AgentServiceUnavailableError" in (saved.error_message or "")


@pytest.mark.anyio
async def test_resume_nvidia_rag_service_none_marks_run_failed() -> None:
    run = _make_waiting_run(AgentType.NVIDIA_RAG)
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ResumeAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        nvidia_rag_service=None,
    )
    await use_case.execute(run_id=run.id, resume_value="ok")

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.FAILED
    assert "AgentServiceUnavailableError" in (saved.error_message or "")
