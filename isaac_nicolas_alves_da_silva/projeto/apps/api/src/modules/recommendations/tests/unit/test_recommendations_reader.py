"""Testes do contrato publico RecommendationsReader."""

from uuid import uuid4

import pytest

from apps.api.src.modules.recommendations.application.use_cases.list_recommendations import (
    ListRecommendations,
)
from apps.api.src.modules.recommendations.domain.entities import Recommendation
from apps.api.src.modules.recommendations.tests.unit.test_generate_recommendations import (
    FakeRecommendationRepository,
    FakeUoW,
)


@pytest.mark.anyio
async def test_list_by_startup_id_returns_views() -> None:
    startup_id = uuid4()
    repository = FakeRecommendationRepository()
    await repository.save(
        Recommendation(
            startup_id=startup_id,
            technology_slug="nvidia-nim",
            technology_name="NVIDIA NIM",
            category="model_serving",
            score=0.8,
            justification="Evidencias mencionam llm e inference.",
        )
    )
    uow = FakeUoW(repository)
    reader = ListRecommendations(lambda: uow)

    views = await reader.list_by_startup_id(startup_id)

    assert len(views) == 1
    assert views[0].technology_slug == "nvidia-nim"


@pytest.mark.anyio
async def test_execute_delegates_to_list_by_startup_id() -> None:
    startup_id = uuid4()
    repository = FakeRecommendationRepository()
    uow = FakeUoW(repository)
    reader = ListRecommendations(lambda: uow)

    views = await reader.execute(startup_id=startup_id)

    assert views == []
