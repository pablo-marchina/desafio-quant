"""Mapper entre AgentStep e AgentStepModel."""

from apps.api.src.modules.agents.domain.entities import AgentStep
from apps.api.src.modules.agents.domain.enums import AgentStepStatus
from apps.api.src.modules.agents.infrastructure.database.models import AgentStepModel


class AgentStepMapper:
    """Mantem dominio e SQLAlchemy desacoplados."""

    @staticmethod
    def to_model(entity: AgentStep) -> AgentStepModel:
        return AgentStepModel(
            id=entity.id,
            run_id=entity.run_id,
            name=entity.name,
            status=entity.status.value,
            input_payload=entity.input_payload,
            output_payload=entity.output_payload,
            error_message=entity.error_message,
            started_at=entity.started_at,
            finished_at=entity.finished_at,
        )

    @staticmethod
    def to_entity(model: AgentStepModel) -> AgentStep:
        return AgentStep(
            id=model.id,
            run_id=model.run_id,
            name=model.name,
            status=AgentStepStatus(model.status),
            input_payload=model.input_payload,
            output_payload=model.output_payload,
            error_message=model.error_message,
            started_at=model.started_at,
            finished_at=model.finished_at,
        )

    @staticmethod
    def update_model(model: AgentStepModel, entity: AgentStep) -> None:
        model.run_id = entity.run_id
        model.name = entity.name
        model.status = entity.status.value
        model.input_payload = entity.input_payload
        model.output_payload = entity.output_payload
        model.error_message = entity.error_message
        model.started_at = entity.started_at
        model.finished_at = entity.finished_at
