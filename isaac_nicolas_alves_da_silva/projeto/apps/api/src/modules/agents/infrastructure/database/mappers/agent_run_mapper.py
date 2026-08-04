"""Mapper entre AgentRun e AgentRunModel."""

from apps.api.src.modules.agents.domain.entities import AgentRun
from apps.api.src.modules.agents.domain.enums import AgentRunStatus, AgentType
from apps.api.src.modules.agents.infrastructure.database.models import AgentRunModel


class AgentRunMapper:
    """Mantem dominio e SQLAlchemy desacoplados."""

    @staticmethod
    def to_model(entity: AgentRun) -> AgentRunModel:
        return AgentRunModel(
            id=entity.id,
            agent_type=entity.agent_type.value,
            status=entity.status.value,
            input_payload=entity.input_payload,
            output_payload=entity.output_payload,
            error_message=entity.error_message,
            created_at=entity.created_at,
            started_at=entity.started_at,
            finished_at=entity.finished_at,
        )

    @staticmethod
    def to_entity(model: AgentRunModel) -> AgentRun:
        return AgentRun(
            id=model.id,
            agent_type=AgentType(model.agent_type),
            status=AgentRunStatus(model.status),
            input_payload=model.input_payload,
            output_payload=model.output_payload,
            error_message=model.error_message,
            created_at=model.created_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
        )

    @staticmethod
    def update_model(model: AgentRunModel, entity: AgentRun) -> None:
        model.agent_type = entity.agent_type.value
        model.status = entity.status.value
        model.input_payload = entity.input_payload
        model.output_payload = entity.output_payload
        model.error_message = entity.error_message
        model.created_at = entity.created_at
        model.started_at = entity.started_at
        model.finished_at = entity.finished_at
