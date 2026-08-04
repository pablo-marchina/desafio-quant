"""Testes integrados dos repositorios de agents contra PostgreSQL."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.database.relational.session import engine
from apps.api.src.modules.agents.domain.entities import AgentRun, AgentStep
from apps.api.src.modules.agents.domain.enums import (
    AgentRunStatus,
    AgentStepStatus,
    AgentType,
)
from apps.api.src.modules.agents.infrastructure.database.repositories.postgres_agent_run_repository import (
    PostgresAgentRunRepository,
)
from apps.api.src.modules.agents.infrastructure.database.repositories.postgres_agent_step_repository import (
    PostgresAgentStepRepository,
)


@pytest.mark.anyio
async def test_postgres_agent_repositories_persist_run_and_steps() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)

        try:
            runs = PostgresAgentRunRepository(session)
            steps = PostgresAgentStepRepository(session)

            run = AgentRun(
                agent_type=AgentType.SEARCH_PLANNING,
                input_payload={"reason": "faltam fontes"},
            )
            await runs.save(run)

            run.start()
            step = AgentStep(
                run_id=run.id,
                name="generate_plan",
                input_payload={"max_queries": 3},
            )
            step.complete({"queries": ["Startup official website"]})
            await steps.save(step)

            run.complete({"queries": ["Startup official website"]})
            await runs.save(run)

            restored_run = await runs.get_by_id(run.id)
            restored_steps = await steps.list_by_run_id(run.id)

            assert restored_run is not None
            assert restored_run.status is AgentRunStatus.COMPLETED
            assert restored_run.agent_type is AgentType.SEARCH_PLANNING
            assert restored_run.output_payload == {
                "queries": ["Startup official website"]
            }

            assert len(restored_steps) == 1
            assert restored_steps[0].status is AgentStepStatus.COMPLETED
            assert restored_steps[0].output_payload == {
                "queries": ["Startup official website"]
            }
        finally:
            await session.close()
            await transaction.rollback()

    await engine.dispose()
