"""Contratos de persistencia do modulo briefing."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.briefing.domain.entities import Briefing


class BriefingRepository(ABC):

    @abstractmethod
    async def save(self, briefing: Briefing) -> None:
        """Cria um briefing."""

    @abstractmethod
    async def delete_by_startup_id(self, startup_id: UUID) -> None:
        """Remove briefings anteriores da startup antes de regenerar."""

    @abstractmethod
    async def get_by_id(self, briefing_id: UUID) -> Briefing | None:
        """Busca briefing por id."""

    @abstractmethod
    async def list_by_startup_id(self, startup_id: UUID) -> list[Briefing]:
        """Lista briefings de uma startup, mais recentes primeiro."""

    @abstractmethod
    async def update_content(self, briefing_id: UUID, content: str) -> None:
        """Atualiza so o conteudo de um briefing ja existente."""

    @abstractmethod
    async def update_review(self, briefing: Briefing) -> None:
        """Atualiza os campos de revisao de um briefing existente."""
