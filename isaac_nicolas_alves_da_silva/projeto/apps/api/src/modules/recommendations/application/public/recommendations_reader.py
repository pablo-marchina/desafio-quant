"""Contrato publico para ler recomendacoes geradas para uma startup."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.recommendations.application.dto import RecommendationView


class RecommendationsReader(ABC):
    """Recomendacoes consultaveis por briefing e outros modulos futuros."""

    @abstractmethod
    async def list_by_startup_id(self, startup_id: UUID) -> list[RecommendationView]:
        """Lista as recomendacoes mais recentes geradas para a startup."""
