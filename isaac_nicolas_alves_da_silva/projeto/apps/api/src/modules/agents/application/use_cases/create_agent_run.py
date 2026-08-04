"""Caso de uso para criar uma execucao assincrona de agente."""

from apps.api.src.modules.agents.application.dto import (
    AgentRunView,
    CreateAgentRunInput,
)
from apps.api.src.modules.agents.application.ports import AgentTaskDispatcher
from apps.api.src.modules.agents.application.unit_of_work import (
    AgentsUnitOfWorkFactory,
)
from apps.api.src.modules.agents.domain.entities import AgentRun
from apps.api.src.modules.agents.domain.exceptions import AgentTaskDispatchError


class CreateAgentRun:
    """Cria um AgentRun, persiste e publica seu id na fila."""

    def __init__(
        self,
        *,
        uow_factory: AgentsUnitOfWorkFactory,
        task_dispatcher: AgentTaskDispatcher,
    ) -> None:
        self.uow_factory = uow_factory
        self.task_dispatcher = task_dispatcher

    async def execute(self, run_input: CreateAgentRunInput) -> AgentRunView:
        run = AgentRun(
            agent_type=run_input.agent_type,
            input_payload=run_input.input_payload,
        )

        async with self.uow_factory() as uow:
            await uow.run_repository.save(run)
            await uow.commit()

        try:
            await self.task_dispatcher.dispatch(run_id=run.id)
        except AgentTaskDispatchError as error:
            async with self.uow_factory() as uow:
                persisted = await uow.run_repository.get_by_id(run.id)
                if persisted is not None:
                    persisted.start()
                    persisted.fail(str(error))
                    await uow.run_repository.save(persisted)
                    await uow.commit()
            raise

        return AgentRunView(
            id=run.id,
            agent_type=run.agent_type,
            status=run.status,
            input_payload=run.input_payload,
            output_payload=run.output_payload,
            error_message=run.error_message,
        )
