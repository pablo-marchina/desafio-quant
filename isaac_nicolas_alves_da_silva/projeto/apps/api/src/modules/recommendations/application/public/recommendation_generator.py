"""Contrato publico para disparar a geracao de recomendacoes de uma startup."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.recommendations.application.dto import RecommendationView


class RecommendationGenerator(ABC):
    """Geracao de recomendacoes consumivel por orchestration e outros modulos."""

    @abstractmethod
    async def generate(self, startup_id: UUID) -> list[RecommendationView]:
        """Gera, persiste e retorna as recomendacoes mais recentes da startup."""
