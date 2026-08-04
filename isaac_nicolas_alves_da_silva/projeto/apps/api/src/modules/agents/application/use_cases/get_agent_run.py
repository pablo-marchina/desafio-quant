"""Caso de uso para consultar uma execucao de agente."""

from uuid import UUID

from apps.api.src.modules.agents.application.dto import AgentRunView
from apps.api.src.modules.agents.application.unit_of_work import (
    AgentsUnitOfWorkFactory,
)
from apps.api.src.modules.agents.domain.exceptions import AgentRunNotFoundError


class GetAgentRun:
    """Consulta um AgentRun persistido."""

    def __init__(self, uow_factory: AgentsUnitOfWorkFactory) -> None:
        self.uow_factory = uow_factory

    async def execute(self, run_id: UUID) -> AgentRunView:
        async with self.uow_factory() as uow:
            run = await uow.run_repository.get_by_id(run_id)

        if run is None:
            raise AgentRunNotFoundError(f"AgentRun {run_id} nao encontrado.")

        return AgentRunView(
            id=run.id,
            agent_type=run.agent_type,
            status=run.status,
            input_payload=run.input_payload,
            output_payload=run.output_payload,
            error_message=run.error_message,
        )
