"""Executor que roteia AgentRun para o grafo correto."""

from apps.api.src.modules.agents.application.agent_run_payloads import (
    evidence_validation_input_from_payload,
    evidence_validation_result_to_payload,
    search_plan_input_from_payload,
    search_plan_result_to_payload,
)
from apps.api.src.modules.agents.application.public.search_planner import (
    SearchPlanningService,
)
from apps.api.src.modules.agents.application.public.semantic_investigator import (
    EvidenceValidationService,
)
from apps.api.src.modules.agents.domain.entities import AgentRun
from apps.api.src.modules.agents.domain.enums import AgentType
from apps.api.src.modules.agents.domain.exceptions import UnsupportedAgentJobError


class AgentRunExecutor:
    """Executa o servico correto de acordo com ``AgentRun.agent_type``."""

    def __init__(
        self,
        *,
        evidence_validation_service: EvidenceValidationService | None,
        search_planning_service: SearchPlanningService | None,
    ) -> None:
        self.evidence_validation_service = evidence_validation_service
        self.search_planning_service = search_planning_service

    async def execute(self, run: AgentRun) -> dict[str, object]:
        """Executa o agente correto e devolve payload serializavel."""

        if run.agent_type is AgentType.EVIDENCE_VALIDATION:
            if self.evidence_validation_service is None:
                raise UnsupportedAgentJobError(
                    "Evidence Validation Agent nao esta configurado."
                )

            result = await self.evidence_validation_service.investigate(
                evidence_validation_input_from_payload(run.input_payload)
            )
            return evidence_validation_result_to_payload(result)

        if run.agent_type is AgentType.SEARCH_PLANNING:
            if self.search_planning_service is None:
                raise UnsupportedAgentJobError(
                    "Search Planner Agent nao esta configurado."
                )

            result = await self.search_planning_service.plan_searches(
                search_plan_input_from_payload(run.input_payload)
            )
            return search_plan_result_to_payload(result)

        raise UnsupportedAgentJobError(
            f"Agent type '{run.agent_type}' nao e suportado."
        )
