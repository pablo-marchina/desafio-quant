"""Adaptador que liga briefing ao contrato publico do modulo recommendations.

Esta e a UNICA peca do modulo ``briefing`` que conhece o modulo
``recommendations`` — e mesmo assim, conhece apenas o contrato publico
(``recommendations/application/public/recommendations_reader.py``).
"""

from uuid import UUID

from apps.api.src.modules.briefing.application.dto import RecommendationSnapshot
from apps.api.src.modules.briefing.application.ports import RecommendationsSource
from apps.api.src.modules.recommendations.application.public.recommendations_reader import (
    RecommendationsReader,
)


class RecommendationsModuleSource(RecommendationsSource):
    """Implementa ``RecommendationsSource`` chamando o modulo recommendations."""

    def __init__(self, reader: RecommendationsReader) -> None:
        self._reader = reader

    async def list_by_startup(self, startup_id: UUID) -> list[RecommendationSnapshot]:
        recommendations = await self._reader.list_by_startup_id(startup_id)
        return [
            RecommendationSnapshot(
                technology_name=recommendation.technology_name,
                category=recommendation.category,
                score=recommendation.score,
                justification=recommendation.justification,
                confidence=recommendation.confidence,
                complexity=recommendation.complexity,
                nivel=recommendation.nivel,
                faltando=tuple(recommendation.faltando),
                signal_origins=tuple(recommendation.signal_origins),
                missing_signals=tuple(recommendation.missing_signals),
            )
            for recommendation in recommendations
        ]
