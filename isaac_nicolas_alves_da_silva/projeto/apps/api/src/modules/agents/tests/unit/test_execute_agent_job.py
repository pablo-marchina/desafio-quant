"""Testes do caso de uso ExecuteAgentJob (Agents V5)."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.agents.application.dto import (
    EvidenceValidationInput,
    EvidenceValidationResult,
    ExtractionInput,
    ExtractionResult,
    NvidiaRagCitation,
    NvidiaRagInput,
    NvidiaRagResult,
    SearchPlanInput,
    SearchPlanResult,
    SearchQuerySuggestion,
    StartupClassificationInput,
    StartupClassificationResult,
)
from apps.api.src.modules.agents.application.public.extractor import (
    ExtractionService,
)
from apps.api.src.modules.agents.application.public.nvidia_rag import (
    NvidiaRagService,
)
from apps.api.src.modules.agents.application.public.search_planner import (
    SearchPlanningService,
)
from apps.api.src.modules.agents.application.public.semantic_investigator import (
    EvidenceValidationService,
)
from apps.api.src.modules.agents.application.public.startup_classifier import (
    StartupClassifierService,
)
from apps.api.src.modules.agents.application.use_cases.execute_agent_job import (
    ExecuteAgentJob,
)
from apps.api.src.modules.agents.domain.entities import AgentRun, AgentStep
from apps.api.src.modules.agents.domain.enums import (
    AgentDecision,
    AgentRunStatus,
    AgentStepStatus,
    AgentType,
    ExtractedFundingStage,
    StartupMaturityLevel,
)
from apps.api.src.modules.agents.domain.exceptions import (
    AgentRunInterruptedError,
    AgentRunNotFoundError,
    AgentServiceUnavailableError,
)

# ---------------------------------------------------------------------------
# Payloads de entrada minimos para cada tipo de agente
# ---------------------------------------------------------------------------

EVIDENCE_VALIDATION_PAYLOAD: dict[str, object] = {
    "url": "https://startup.com/about",
    "title": "About us",
    "raw_text": "We build AI-powered solutions for enterprise customers.",
    "technical_score": 0.9,
    "text_score": 0.8,
    "evidence_score": 0.6,
    "quality_score": 0.73,
}

SEARCH_PLANNING_PAYLOAD: dict[str, object] = {
    "startup_name": "Acme AI",
    "source_url": "https://acme.com",
    "source_title": "Home",
    "raw_text": "We use AI to improve operations.",
    "reason": "Evidence is generic, need more sources.",
}

STARTUP_CLASSIFICATION_PAYLOAD: dict[str, object] = {
    "name": "Acme AI",
    "sector": "LLM customer service",
    "description": "Plataforma de atendimento com LLM proprietario.",
    "country": "BR",
    "website_url": "https://acme.example.com",
    "evidence_texts": ["Acme treina modelos proprios de LLM."],
}

EXTRACTION_PAYLOAD: dict[str, object] = {
    "name": "Acme AI",
    "sector": "LLM customer service",
    "description": "Plataforma de atendimento com LLM proprietario.",
    "evidence_texts": ["Acme foi fundada por Ana Silva, Series A de USD 2M."],
}

NVIDIA_RAG_PAYLOAD: dict[str, object] = {
    "query": "O que e o NVIDIA NIM?",
    "limit": 3,
}


# ---------------------------------------------------------------------------
# Fakes de infraestrutura
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
        self.committed = False

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
        self.committed = True

    async def rollback(self) -> None:
        return None


# ---------------------------------------------------------------------------
# Fakes dos servicos de grafo
# ---------------------------------------------------------------------------


class FakeEvidenceValidationService(EvidenceValidationService):
    async def investigate(
        self,
        investigation_input: EvidenceValidationInput,
        *,
        thread_id: str | None = None,
    ) -> EvidenceValidationResult:
        return EvidenceValidationResult(
            decision=AgentDecision.ACCEPTED,
            reason="Conteudo validado pelo fake.",
        )


class FakeSearchPlanningService(SearchPlanningService):
    async def plan_searches(
        self,
        plan_input: SearchPlanInput,
        *,
        thread_id: str | None = None,
    ) -> SearchPlanResult:
        return SearchPlanResult(
            queries=[
                SearchQuerySuggestion(
                    query="Acme AI startup use case",
                    purpose="Encontrar evidencias adicionais",
                    priority=1,
                )
            ],
            reason="Plano gerado pelo fake.",
        )


class FakeStartupClassificationService(StartupClassifierService):
    async def classify(
        self,
        classification_input: StartupClassificationInput,
        *,
        thread_id: str | None = None,
    ) -> StartupClassificationResult:
        return StartupClassificationResult(
            level=StartupMaturityLevel.AI_NATIVE,
            reason="Classificado pelo fake.",
        )


class FakeExtractionService(ExtractionService):
    async def extract(
        self,
        extraction_input: ExtractionInput,
        *,
        thread_id: str | None = None,
    ) -> ExtractionResult:
        return ExtractionResult(
            founders=["Ana Silva"],
            funding_stage=ExtractedFundingStage.SERIES_A,
            funding_amount_usd=2_000_000.0,
            customers=[],
        )


class FakeNvidiaRagService(NvidiaRagService):
    async def answer(
        self,
        rag_input: NvidiaRagInput,
        *,
        thread_id: str | None = None,
    ) -> NvidiaRagResult:
        return NvidiaRagResult(
            answer="NIM e um microservico de inferencia da NVIDIA.",
            citations=[
                NvidiaRagCitation(
                    source_url="https://docs.nvidia.com/nim/",
                    quote="NIM e um microservico de inferencia.",
                )
            ],
        )


class FailingEvidenceValidationService(EvidenceValidationService):
    async def investigate(
        self,
        investigation_input: EvidenceValidationInput,
        *,
        thread_id: str | None = None,
    ) -> EvidenceValidationResult:
        raise RuntimeError("LLM timeout simulado")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_uow_factory(
    runs: dict[UUID, AgentRun], steps: FakeStepRepository
):
    return lambda: FakeAgentsUnitOfWork(runs, steps)


# ---------------------------------------------------------------------------
# Testes — Evidence Validation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_evidence_validation_run_completes_with_real_output() -> None:
    run = AgentRun(
        id=uuid4(),
        agent_type=AgentType.EVIDENCE_VALIDATION,
        input_payload=EVIDENCE_VALIDATION_PAYLOAD,
    )
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        evidence_validation_service=FakeEvidenceValidationService(),
    )
    await use_case.execute(run_id=run.id)

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.COMPLETED
    assert saved.output_payload is not None
    assert saved.output_payload["decision"] == AgentDecision.ACCEPTED.value
    assert saved.output_payload["reason"] == "Conteudo validado pelo fake."

    assert len(steps.steps) == 1
    step = steps.steps[0]
    assert step.name == "execute_evidence_validation"
    assert step.status is AgentStepStatus.COMPLETED
    assert step.output_payload == saved.output_payload


@pytest.mark.anyio
async def test_evidence_validation_service_none_marks_run_failed() -> None:
    run = AgentRun(
        id=uuid4(),
        agent_type=AgentType.EVIDENCE_VALIDATION,
        input_payload=EVIDENCE_VALIDATION_PAYLOAD,
    )
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        evidence_validation_service=None,
    )
    await use_case.execute(run_id=run.id)

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.FAILED
    assert saved.error_message is not None
    assert "AgentServiceUnavailableError" in saved.error_message

    step = steps.steps[0]
    assert step.status is AgentStepStatus.FAILED


@pytest.mark.anyio
async def test_evidence_validation_llm_failure_marks_run_failed() -> None:
    run = AgentRun(
        id=uuid4(),
        agent_type=AgentType.EVIDENCE_VALIDATION,
        input_payload=EVIDENCE_VALIDATION_PAYLOAD,
    )
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        evidence_validation_service=FailingEvidenceValidationService(),
    )
    await use_case.execute(run_id=run.id)

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.FAILED
    assert "LLM timeout simulado" in (saved.error_message or "")

    step = steps.steps[0]
    assert step.status is AgentStepStatus.FAILED


# ---------------------------------------------------------------------------
# Testes — Search Planning
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_search_planning_run_completes_with_real_output() -> None:
    run = AgentRun(
        id=uuid4(),
        agent_type=AgentType.SEARCH_PLANNING,
        input_payload=SEARCH_PLANNING_PAYLOAD,
    )
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        search_planning_service=FakeSearchPlanningService(),
    )
    await use_case.execute(run_id=run.id)

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.COMPLETED
    assert saved.output_payload is not None
    assert isinstance(saved.output_payload["queries"], list)
    assert len(saved.output_payload["queries"]) == 1
    assert saved.output_payload["reason"] == "Plano gerado pelo fake."

    step = steps.steps[0]
    assert step.name == "execute_search_planning"
    assert step.status is AgentStepStatus.COMPLETED


@pytest.mark.anyio
async def test_search_planning_service_none_marks_run_failed() -> None:
    run = AgentRun(
        id=uuid4(),
        agent_type=AgentType.SEARCH_PLANNING,
        input_payload=SEARCH_PLANNING_PAYLOAD,
    )
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        search_planning_service=None,
    )
    await use_case.execute(run_id=run.id)

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.FAILED
    assert "AgentServiceUnavailableError" in (saved.error_message or "")


# ---------------------------------------------------------------------------
# Testes — Startup Classification (V9)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_startup_classification_run_completes_with_real_output() -> None:
    run = AgentRun(
        id=uuid4(),
        agent_type=AgentType.STARTUP_CLASSIFIER,
        input_payload=STARTUP_CLASSIFICATION_PAYLOAD,
    )
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        startup_classification_service=FakeStartupClassificationService(),
    )
    await use_case.execute(run_id=run.id)

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.COMPLETED
    assert saved.output_payload is not None
    assert saved.output_payload["level"] == StartupMaturityLevel.AI_NATIVE.value
    assert saved.output_payload["reason"] == "Classificado pelo fake."

    step = steps.steps[0]
    assert step.name == "execute_startup_classifier"
    assert step.status is AgentStepStatus.COMPLETED


@pytest.mark.anyio
async def test_startup_classification_service_none_marks_run_failed() -> None:
    run = AgentRun(
        id=uuid4(),
        agent_type=AgentType.STARTUP_CLASSIFIER,
        input_payload=STARTUP_CLASSIFICATION_PAYLOAD,
    )
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        startup_classification_service=None,
    )
    await use_case.execute(run_id=run.id)

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.FAILED
    assert "AgentServiceUnavailableError" in (saved.error_message or "")


# ---------------------------------------------------------------------------
# Testes — Extraction (V8)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_extraction_run_completes_with_real_output() -> None:
    run = AgentRun(
        id=uuid4(),
        agent_type=AgentType.EXTRACTION,
        input_payload=EXTRACTION_PAYLOAD,
    )
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        extraction_service=FakeExtractionService(),
    )
    await use_case.execute(run_id=run.id)

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.COMPLETED
    assert saved.output_payload is not None
    assert saved.output_payload["founders"] == ["Ana Silva"]
    assert saved.output_payload["funding_stage"] == ExtractedFundingStage.SERIES_A.value

    step = steps.steps[0]
    assert step.name == "execute_extraction"
    assert step.status is AgentStepStatus.COMPLETED


@pytest.mark.anyio
async def test_extraction_service_none_marks_run_failed() -> None:
    run = AgentRun(
        id=uuid4(),
        agent_type=AgentType.EXTRACTION,
        input_payload=EXTRACTION_PAYLOAD,
    )
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        extraction_service=None,
    )
    await use_case.execute(run_id=run.id)

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.FAILED
    assert "AgentServiceUnavailableError" in (saved.error_message or "")


# ---------------------------------------------------------------------------
# Testes — Casos gerais
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_execute_raises_when_run_does_not_exist() -> None:
    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory({}, FakeStepRepository()),
    )
    with pytest.raises(AgentRunNotFoundError):
        await use_case.execute(run_id=uuid4())


@pytest.mark.anyio
async def test_step_records_agent_type_in_input_payload() -> None:
    run = AgentRun(
        id=uuid4(),
        agent_type=AgentType.SEARCH_PLANNING,
        input_payload=SEARCH_PLANNING_PAYLOAD,
    )
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        search_planning_service=FakeSearchPlanningService(),
    )
    await use_case.execute(run_id=run.id)

    step = steps.steps[0]
    assert step.input_payload is not None
    assert step.input_payload["agent_type"] == AgentType.SEARCH_PLANNING.value
    assert "run_id" in step.input_payload


# ---------------------------------------------------------------------------
# V6: interrupt handling
# ---------------------------------------------------------------------------


class InterruptingEvidenceValidationService(EvidenceValidationService):
    """Simula um grafo que pausa aguardando aprovacao humana."""

    async def investigate(
        self,
        investigation_input: EvidenceValidationInput,
        *,
        thread_id: str | None = None,
    ) -> EvidenceValidationResult:
        raise AgentRunInterruptedError("approve or reject?")


@pytest.mark.anyio
async def test_graph_interrupt_transitions_run_to_waiting_human_review() -> None:
    run = AgentRun(
        id=uuid4(),
        agent_type=AgentType.EVIDENCE_VALIDATION,
        input_payload=EVIDENCE_VALIDATION_PAYLOAD,
    )
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        evidence_validation_service=InterruptingEvidenceValidationService(),
    )
    await use_case.execute(run_id=run.id)

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.WAITING_HUMAN_REVIEW
    assert saved.output_payload is not None
    assert saved.output_payload.get("interrupt_value") == "approve or reject?"

    step = steps.steps[0]
    assert step.status is AgentStepStatus.COMPLETED
    assert step.output_payload is not None
    assert step.output_payload.get("status") == "interrupted"


@pytest.mark.anyio
async def test_thread_id_equals_run_id_string() -> None:
    """thread_id passado ao servico deve ser o UUID do run como string."""

    received_thread_ids: list[str | None] = []

    class CapturingService(EvidenceValidationService):
        async def investigate(
            self,
            investigation_input: EvidenceValidationInput,
            *,
            thread_id: str | None = None,
        ) -> EvidenceValidationResult:
            received_thread_ids.append(thread_id)
            return EvidenceValidationResult(
                decision=AgentDecision.ACCEPTED,
                reason="captured",
            )

    run = AgentRun(
        id=uuid4(),
        agent_type=AgentType.EVIDENCE_VALIDATION,
        input_payload=EVIDENCE_VALIDATION_PAYLOAD,
    )
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        evidence_validation_service=CapturingService(),
    )
    await use_case.execute(run_id=run.id)

    assert len(received_thread_ids) == 1
    assert received_thread_ids[0] == str(run.id)


# ---------------------------------------------------------------------------
# Testes — NVIDIA RAG Agent (V10)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_nvidia_rag_run_completes_with_real_output() -> None:
    run = AgentRun(
        id=uuid4(),
        agent_type=AgentType.NVIDIA_RAG,
        input_payload=NVIDIA_RAG_PAYLOAD,
    )
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        nvidia_rag_service=FakeNvidiaRagService(),
    )
    await use_case.execute(run_id=run.id)

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.COMPLETED
    assert saved.output_payload is not None
    assert saved.output_payload["answer"] == (
        "NIM e um microservico de inferencia da NVIDIA."
    )
    assert saved.output_payload["citations"] == [
        {
            "source_url": "https://docs.nvidia.com/nim/",
            "quote": "NIM e um microservico de inferencia.",
        }
    ]

    step = steps.steps[0]
    assert step.name == "execute_nvidia_rag"
    assert step.status is AgentStepStatus.COMPLETED


@pytest.mark.anyio
async def test_nvidia_rag_service_none_marks_run_failed() -> None:
    run = AgentRun(
        id=uuid4(),
        agent_type=AgentType.NVIDIA_RAG,
        input_payload=NVIDIA_RAG_PAYLOAD,
    )
    runs = {run.id: run}
    steps = FakeStepRepository()

    use_case = ExecuteAgentJob(
        uow_factory=make_uow_factory(runs, steps),
        nvidia_rag_service=None,
    )
    await use_case.execute(run_id=run.id)

    saved = runs[run.id]
    assert saved.status is AgentRunStatus.FAILED
    assert "AgentServiceUnavailableError" in (saved.error_message or "")
