"""Caso de uso para retomar um AgentRun pausado por interrupcao humana."""

from uuid import UUID

from apps.api.src.modules.agents.application.agent_run_payloads import (
    briefing_agent_result_to_payload,
    evidence_validation_result_to_payload,
    extraction_result_to_payload,
    nvidia_rag_result_to_payload,
    recommendation_agent_result_to_payload,
    search_plan_result_to_payload,
    startup_classification_result_to_payload,
)
from apps.api.src.modules.agents.application.public.briefing_agent import (
    BriefingAgentService,
)
from apps.api.src.modules.agents.application.public.extractor import (
    ExtractionService,
)
from apps.api.src.modules.agents.application.public.nvidia_rag import (
    NvidiaRagService,
)
from apps.api.src.modules.agents.application.public.recommendation_agent import (
    RecommendationAgentService,
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
from apps.api.src.modules.agents.application.unit_of_work import (
    AgentsUnitOfWorkFactory,
)
from apps.api.src.modules.agents.domain.entities import AgentStep
from apps.api.src.modules.agents.domain.enums import AgentRunStatus, AgentType
from apps.api.src.modules.agents.domain.exceptions import (
    AgentRunInterruptedError,
    AgentRunNotFoundError,
    AgentServiceUnavailableError,
    UnsupportedAgentJobError,
)


class ResumeAgentJob:
    """Retoma uma execucao pausada em ``waiting_human_review``.

    Recebe a decisao humana (``resume_value``), reativa o AgentRun, chama o
    metodo ``resume()`` do servico correspondente — que retoma o grafo LangGraph
    a partir do checkpoint PostgreSQL — e persiste o resultado ou nova interrupcao.
    """

    def __init__(
        self,
        uow_factory: AgentsUnitOfWorkFactory,
        evidence_validation_service: EvidenceValidationService | None = None,
        search_planning_service: SearchPlanningService | None = None,
        startup_classification_service: StartupClassifierService | None = None,
        extraction_service: ExtractionService | None = None,
        nvidia_rag_service: NvidiaRagService | None = None,
        recommendation_agent_service: RecommendationAgentService | None = None,
        briefing_agent_service: BriefingAgentService | None = None,
    ) -> None:
        self.uow_factory = uow_factory
        self.evidence_validation_service = evidence_validation_service
        self.search_planning_service = search_planning_service
        self.startup_classification_service = startup_classification_service
        self.extraction_service = extraction_service
        self.nvidia_rag_service = nvidia_rag_service
        self.recommendation_agent_service = recommendation_agent_service
        self.briefing_agent_service = briefing_agent_service

    async def execute(self, *, run_id: UUID, resume_value: object) -> None:
        async with self.uow_factory() as uow:
            run = await uow.run_repository.get_by_id(run_id)
            if run is None:
                raise AgentRunNotFoundError(f"AgentRun {run_id} nao encontrado.")

            if run.status is not AgentRunStatus.WAITING_HUMAN_REVIEW:
                raise AgentRunNotFoundError(
                    f"AgentRun {run_id} nao esta aguardando revisao humana "
                    f"(status atual: {run.status})."
                )

            run.resume()
            step = AgentStep(
                run_id=run.id,
                name=f"resume_{run.agent_type.value}",
                input_payload={
                    "agent_type": run.agent_type.value,
                    "run_id": str(run_id),
                    "resume_value": str(resume_value),
                },
            )

            try:
                output_payload = await self._resume_graph(
                    run.agent_type, thread_id=str(run.id), resume_value=resume_value
                )
                step.complete(output_payload)
                run.complete(output_payload)
            except AgentRunInterruptedError as exc:
                # Grafo pausou novamente (multiplos pontos de revisao).
                interrupt_value = str(exc)
                run.interrupt(interrupt_value)
                step.complete({"status": "interrupted", "interrupt_value": interrupt_value})
            except Exception as exc:
                reason = f"{type(exc).__name__}: {exc}"
                step.fail(reason)
                run.fail(reason)

            await uow.run_repository.save(run)
            await uow.step_repository.save(step)
            await uow.commit()

    async def _resume_graph(
        self,
        agent_type: AgentType,
        *,
        thread_id: str,
        resume_value: object,
    ) -> dict[str, object]:
        if agent_type is AgentType.EVIDENCE_VALIDATION:
            if self.evidence_validation_service is None:
                raise AgentServiceUnavailableError(
                    "Evidence validation service nao configurado."
                )
            result = await self.evidence_validation_service.resume(thread_id, resume_value)
            return evidence_validation_result_to_payload(result)

        if agent_type is AgentType.SEARCH_PLANNING:
            if self.search_planning_service is None:
                raise AgentServiceUnavailableError(
                    "Search planning service nao configurado."
                )
            result = await self.search_planning_service.resume(thread_id, resume_value)
            return search_plan_result_to_payload(result)

        if agent_type is AgentType.STARTUP_CLASSIFIER:
            if self.startup_classification_service is None:
                raise AgentServiceUnavailableError(
                    "Startup classification service nao configurado."
                )
            result = await self.startup_classification_service.resume(
                thread_id, resume_value
            )
            return startup_classification_result_to_payload(result)

        if agent_type is AgentType.EXTRACTION:
            if self.extraction_service is None:
                raise AgentServiceUnavailableError(
                    "Extraction service nao configurado."
                )
            result = await self.extraction_service.resume(thread_id, resume_value)
            return extraction_result_to_payload(result)

        if agent_type is AgentType.NVIDIA_RAG:
            if self.nvidia_rag_service is None:
                raise AgentServiceUnavailableError(
                    "NVIDIA RAG service nao configurado."
                )
            result = await self.nvidia_rag_service.resume(thread_id, resume_value)
            return nvidia_rag_result_to_payload(result)

        if agent_type is AgentType.RECOMMENDATION:
            if self.recommendation_agent_service is None:
                raise AgentServiceUnavailableError(
                    "Recommendation agent service nao configurado."
                )
            result = await self.recommendation_agent_service.resume(
                thread_id, resume_value
            )
            return recommendation_agent_result_to_payload(result)

        if agent_type is AgentType.BRIEFING:
            if self.briefing_agent_service is None:
                raise AgentServiceUnavailableError(
                    "Briefing agent service nao configurado."
                )
            result = await self.briefing_agent_service.resume(
                thread_id, resume_value
            )
            return briefing_agent_result_to_payload(result)

        raise UnsupportedAgentJobError(
            f"Agent type '{agent_type}' ainda nao tem grafo configurado."
        )
