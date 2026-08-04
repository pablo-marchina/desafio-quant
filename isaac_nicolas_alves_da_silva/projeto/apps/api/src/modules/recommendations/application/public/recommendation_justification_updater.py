"""Contrato publico para atualizar a justificativa de recomendacoes existentes."""

from abc import ABC, abstractmethod
from uuid import UUID


class RecommendationJustificationUpdater(ABC):
    """Atualiza so a justificativa de recomendacoes ja persistidas.

    Usado pelo Recommendation Agent (``agents`` V11) para gravar a
    justificativa revisada em linguagem de negocio, sem recalcular score
    nem reimplementar ``match_technologies()``.
    """

    @abstractmethod
    async def update_justifications(
        self, startup_id: UUID, justifications: dict[str, str]
    ) -> None:
        """Atualiza a justificativa das recomendacoes cujo ``technology_slug``
        aparecer em ``justifications``; ignora slugs nao encontrados."""
