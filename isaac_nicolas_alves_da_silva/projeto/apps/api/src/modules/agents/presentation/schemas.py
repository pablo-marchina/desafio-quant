"""Schemas Pydantic da presentation layer do modulo agents."""

from uuid import UUID

from pydantic import BaseModel


class AgentRunResponse(BaseModel):
    """Representacao HTTP de uma execucao de agente."""

    id: UUID
    agent_type: str
    status: str
    output_payload: dict | None = None
    error_message: str | None = None
    interrupt_value: str | None = None

    @classmethod
    def from_view(cls, view) -> "AgentRunResponse":
        """Constroi resposta a partir de AgentRunView, extraindo interrupt_value."""

        interrupt_value: str | None = None
        if view.output_payload and "interrupt_value" in view.output_payload:
            interrupt_value = str(view.output_payload["interrupt_value"])

        return cls(
            id=view.id,
            agent_type=view.agent_type.value,
            status=view.status.value,
            output_payload=view.output_payload,
            error_message=view.error_message,
            interrupt_value=interrupt_value,
        )


class ResumeAgentRunRequest(BaseModel):
    """Corpo da requisicao para retomar um run pausado.

    ``resume_value`` e a decisao do revisor humano. Para o
    EvidenceValidationGraph, os valores esperados sao ``'approved'`` ou
    ``'rejected'``, mas o campo e livre para suportar futuros agentes.
    """

    resume_value: str
