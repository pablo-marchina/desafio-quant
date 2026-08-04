"""Repositorio PostgreSQL de AgentStep."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.agents.domain.entities import AgentStep
from apps.api.src.modules.agents.domain.repositories import AgentStepRepository
from apps.api.src.modules.agents.infrastructure.database.mappers.agent_step_mapper import (
    AgentStepMapper,
)
from apps.api.src.modules.agents.infrastructure.database.models import AgentStepModel


class PostgresAgentStepRepository(AgentStepRepository):
    """Persiste etapas de agents usando SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, step: AgentStep) -> None:
        model = await self.session.get(AgentStepModel, step.id)

        if model is None:
            self.session.add(AgentStepMapper.to_model(step))
        else:
            AgentStepMapper.update_model(model, step)

        await self.session.flush()

    async def list_by_run_id(self, run_id: UUID) -> list[AgentStep]:
        result = await self.session.scalars(
            select(AgentStepModel)
            .where(AgentStepModel.run_id == run_id)
            .order_by(AgentStepModel.started_at.asc())
        )

        return [AgentStepMapper.to_entity(model) for model in result.all()]
