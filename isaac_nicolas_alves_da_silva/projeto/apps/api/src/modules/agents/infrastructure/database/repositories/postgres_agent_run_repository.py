"""Repositorio PostgreSQL de AgentRun."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.agents.domain.entities import AgentRun
from apps.api.src.modules.agents.domain.repositories import AgentRunRepository
from apps.api.src.modules.agents.infrastructure.database.mappers.agent_run_mapper import (
    AgentRunMapper,
)
from apps.api.src.modules.agents.infrastructure.database.models import AgentRunModel


class PostgresAgentRunRepository(AgentRunRepository):
    """Persiste execucoes de agentes usando SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, run: AgentRun) -> None:
        model = await self.session.get(AgentRunModel, run.id)

        if model is None:
            self.session.add(AgentRunMapper.to_model(run))
        else:
            AgentRunMapper.update_model(model, run)

        await self.session.flush()

    async def get_by_id(self, run_id: UUID) -> AgentRun | None:
        model = await self.session.get(AgentRunModel, run_id)
        if model is None:
            return None

        return AgentRunMapper.to_entity(model)
