"""Contratos de persistencia do modulo recommendations."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.recommendations.domain.entities import Recommendation


class RecommendationRepository(ABC):

    @abstractmethod
    async def save(self, recommendation: Recommendation) -> None:
        """Cria uma recomendacao."""

    @abstractmethod
    async def delete_by_startup_id(self, startup_id: UUID) -> None:
        """Remove recomendacoes anteriores da startup antes de regenerar."""

    @abstractmethod
    async def get_by_id(self, recommendation_id: UUID) -> Recommendation | None:
        """Busca recomendacao por id."""

    @abstractmethod
    async def list_by_startup_id(self, startup_id: UUID) -> list[Recommendation]:
        """Lista recomendacoes de uma startup, ordenadas por score."""

    @abstractmethod
    async def update_justification(
        self, recommendation_id: UUID, justification: str
    ) -> None:
        """Atualiza so a justificativa de uma recomendacao ja existente."""

    @abstractmethod
    async def update_review(self, recommendation: Recommendation) -> None:
        """Atualiza os campos de revisao de uma recomendacao existente."""

    @abstractmethod
    async def count_by_technology(self, *, limit: int = 10) -> list[tuple[str, str, int]]:
        """Retorna as tecnologias mais recomendadas.

        Cada elemento: (technology_slug, technology_name, count).
        Ordenado por count DESC, limitado a `limit` itens.
        """
