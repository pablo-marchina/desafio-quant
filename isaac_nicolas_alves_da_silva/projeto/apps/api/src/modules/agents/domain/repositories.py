"""Contratos de persistencia do modulo agents."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.agents.domain.entities import AgentRun, AgentStep


class AgentRunRepository(ABC):
    """Contrato para salvar e consultar execucoes de agentes."""

    @abstractmethod
    async def save(self, run: AgentRun) -> None:
        """Cria ou atualiza uma execucao."""

    @abstractmethod
    async def get_by_id(self, run_id: UUID) -> AgentRun | None:
        """Retorna a execucao correspondente ou ``None``."""


class AgentStepRepository(ABC):
    """Contrato para registrar etapas de uma execucao."""

    @abstractmethod
    async def save(self, step: AgentStep) -> None:
        """Cria ou atualiza uma etapa."""

    @abstractmethod
    async def list_by_run_id(self, run_id: UUID) -> list[AgentStep]:
        """Lista etapas pertencentes a uma execucao."""
