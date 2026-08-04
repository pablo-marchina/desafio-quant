"""Adaptador que implementa RecommendationToolPort usando o contrato
publico de ``recommendations``.

Nao importa nada de ``recommendations`` alem de ``application/public/`` e
``application/dto.py`` — as instancias de ``RecommendationGenerator`` e
``RecommendationJustificationUpdater`` sao construidas pela
``RecommendationsFactory`` e injetadas aqui.
"""

from uuid import UUID

from apps.api.src.modules.agents.application.dto import RecommendationCandidate
from apps.api.src.modules.agents.application.ports import RecommendationToolPort
from apps.api.src.modules.agents.domain.exceptions import AgentRecommendationError
from apps.api.src.modules.recommendations.application.public.recommendation_generator import (
    RecommendationGenerator,
)
from apps.api.src.modules.recommendations.application.public.recommendation_justification_updater import (
    RecommendationJustificationUpdater,
)
from apps.api.src.modules.recommendations.domain.exceptions import RecommendationError


class RecommendationGeneratorAdapter(RecommendationToolPort):

    def __init__(
        self,
        generator: RecommendationGenerator,
        justification_updater: RecommendationJustificationUpdater,
    ) -> None:
        self._generator = generator
        self._justification_updater = justification_updater

    async def generate(self, startup_id: UUID) -> list[RecommendationCandidate]:
        try:
            views = await self._generator.generate(startup_id)
        except RecommendationError as error:
            raise AgentRecommendationError(
                f"Geracao de recomendacoes falhou: {error}"
            ) from error

        return [
            RecommendationCandidate(
                technology_slug=view.technology_slug,
                technology_name=view.technology_name,
                category=view.category,
                score=view.score,
                justification=view.justification,
                matched_keywords=list(view.matched_keywords),
            )
            for view in views
        ]

    async def update_justifications(
        self, startup_id: UUID, justifications: dict[str, str]
    ) -> None:
        try:
            await self._justification_updater.update_justifications(
                startup_id, justifications
            )
        except RecommendationError as error:
            raise AgentRecommendationError(
                f"Atualizacao de justificativa falhou: {error}"
            ) from error
