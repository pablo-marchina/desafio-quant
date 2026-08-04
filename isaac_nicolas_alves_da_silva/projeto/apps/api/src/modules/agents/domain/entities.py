"""Entidades do modulo agents.

Estas classes representam execucoes persistidas de agentes. Elas nao conhecem
SQLAlchemy, Dramatiq, LangGraph ou Gemini; guardam apenas dados e regras de
transicao de estado.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.api.src.modules.agents.domain.enums import (
    AgentRunStatus,
    AgentStepStatus,
    AgentType,
)
from apps.api.src.modules.agents.domain.exceptions import (
    InvalidAgentRunTransitionError,
    InvalidAgentStepTransitionError,
)


def utc_now() -> datetime:
    """Retorna o horario atual em UTC."""

    return datetime.now(UTC)


JsonDict = dict[str, object]


@dataclass
class AgentRun:
    """Representa uma execucao completa de um agente."""

    agent_type: AgentType
    input_payload: JsonDict
    id: UUID = field(default_factory=uuid4)
    status: AgentRunStatus = AgentRunStatus.PENDING
    output_payload: JsonDict | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def start(self) -> None:
        """Marca a execucao como iniciada."""

        if self.status is not AgentRunStatus.PENDING:
            raise InvalidAgentRunTransitionError(
                f"Somente agent runs pendentes podem iniciar. Estado atual: {self.status}."
            )

        self.status = AgentRunStatus.RUNNING
        self.started_at = utc_now()

    def complete(self, output_payload: JsonDict) -> None:
        """Conclui a execucao com uma saida estruturada."""

        if self.status is not AgentRunStatus.RUNNING:
            raise InvalidAgentRunTransitionError(
                f"Somente agent runs em execucao podem concluir. Estado atual: {self.status}."
            )

        self.status = AgentRunStatus.COMPLETED
        self.output_payload = output_payload
        self.finished_at = utc_now()

    def fail(self, reason: str) -> None:
        """Conclui a execucao com falha conhecida."""

        if self.status is not AgentRunStatus.RUNNING:
            raise InvalidAgentRunTransitionError(
                f"Somente agent runs em execucao podem falhar. Estado atual: {self.status}."
            )

        self.status = AgentRunStatus.FAILED
        self.error_message = reason
        self.finished_at = utc_now()

    def interrupt(self, interrupt_value: str) -> None:
        """Pausa a execucao aguardando decisao humana.

        O valor de interrupcao (pergunta ou contexto para o revisor) e
        armazenado em ``output_payload`` para que a API possa exibi-lo.
        """

        if self.status is not AgentRunStatus.RUNNING:
            raise InvalidAgentRunTransitionError(
                f"Somente agent runs em execucao podem ser interrompidos. Estado atual: {self.status}."
            )

        self.status = AgentRunStatus.WAITING_HUMAN_REVIEW
        self.output_payload = {"interrupt_value": interrupt_value}

    def resume(self) -> None:
        """Retoma a execucao apos decisao humana."""

        if self.status is not AgentRunStatus.WAITING_HUMAN_REVIEW:
            raise InvalidAgentRunTransitionError(
                f"Somente agent runs aguardando revisao podem ser retomados. Estado atual: {self.status}."
            )

        self.status = AgentRunStatus.RUNNING
        self.output_payload = None
        self.started_at = utc_now()


@dataclass
class AgentStep:
    """Representa uma etapa auditavel dentro de um AgentRun."""

    run_id: UUID
    name: str
    id: UUID = field(default_factory=uuid4)
    status: AgentStepStatus = AgentStepStatus.RUNNING
    input_payload: JsonDict | None = None
    output_payload: JsonDict | None = None
    error_message: str | None = None
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime | None = None

    def complete(self, output_payload: JsonDict | None = None) -> None:
        """Finaliza a etapa com sucesso."""

        if self.status is not AgentStepStatus.RUNNING:
            raise InvalidAgentStepTransitionError(
                f"Somente etapas em execucao podem concluir. Estado atual: {self.status}."
            )

        self.status = AgentStepStatus.COMPLETED
        self.output_payload = output_payload
        self.finished_at = utc_now()

    def fail(self, reason: str) -> None:
        """Finaliza a etapa com falha."""

        if self.status is not AgentStepStatus.RUNNING:
            raise InvalidAgentStepTransitionError(
                f"Somente etapas em execucao podem falhar. Estado atual: {self.status}."
            )

        self.status = AgentStepStatus.FAILED
        self.error_message = reason
        self.finished_at = utc_now()
