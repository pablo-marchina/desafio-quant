"""Testes dos mappers de agent_runs e agent_steps."""

from apps.api.src.modules.agents.domain.entities import AgentRun, AgentStep
from apps.api.src.modules.agents.domain.enums import AgentType
from apps.api.src.modules.agents.infrastructure.database.mappers.agent_run_mapper import (
    AgentRunMapper,
)
from apps.api.src.modules.agents.infrastructure.database.mappers.agent_step_mapper import (
    AgentStepMapper,
)


def test_agent_run_mapper_roundtrip() -> None:
    run = AgentRun(
        agent_type=AgentType.SEARCH_PLANNING,
        input_payload={"reason": "faltam fontes"},
    )

    model = AgentRunMapper.to_model(run)
    entity = AgentRunMapper.to_entity(model)

    assert entity.id == run.id
    assert entity.agent_type is AgentType.SEARCH_PLANNING
    assert entity.input_payload == {"reason": "faltam fontes"}


def test_agent_step_mapper_roundtrip() -> None:
    run = AgentRun(agent_type=AgentType.SEARCH_PLANNING, input_payload={})
    step = AgentStep(
        run_id=run.id,
        name="worker_received",
        input_payload={"agent_type": "search_planning"},
    )

    model = AgentStepMapper.to_model(step)
    entity = AgentStepMapper.to_entity(model)

    assert entity.id == step.id
    assert entity.run_id == run.id
    assert entity.name == "worker_received"
    assert entity.input_payload == {"agent_type": "search_planning"}
