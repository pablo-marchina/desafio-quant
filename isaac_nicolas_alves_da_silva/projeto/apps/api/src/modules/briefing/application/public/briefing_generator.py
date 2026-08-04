"""Contrato publico para disparar a geracao do briefing de uma startup."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.briefing.application.dto import BriefingView


class BriefingGenerator(ABC):
    """Geracao de briefing consumivel por orchestration e outros modulos."""

    @abstractmethod
    async def generate(self, startup_id: UUID) -> BriefingView:
        """Gera, persiste e retorna o briefing mais recente da startup."""
