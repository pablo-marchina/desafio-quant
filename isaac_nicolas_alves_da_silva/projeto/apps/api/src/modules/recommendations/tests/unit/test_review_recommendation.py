"""Testes do caso de uso ReviewRecommendation."""

from uuid import uuid4

import pytest

from apps.api.src.modules.recommendations.application.dto import (
    ReviewRecommendationInput,
)
from apps.api.src.modules.recommendations.application.use_cases.review_recommendation import (
    ReviewRecommendation,
)
from apps.api.src.modules.recommendations.domain.entities import Recommendation
from apps.api.src.modules.recommendations.tests.unit.test_generate_recommendations import (
    FakeRecommendationRepository,
    FakeUoW,
)


@pytest.mark.anyio
async def test_review_recommendation_approves_with_comment() -> None:
    recommendation = Recommendation(
        startup_id=uuid4(),
        technology_slug="nvidia-nim",
        technology_name="NVIDIA NIM",
        category="model_serving",
        score=0.8,
        justification="Justificativa.",
    )
    repository = FakeRecommendationRepository()
    await repository.save(recommendation)
    uow = FakeUoW(repository)

    view = await ReviewRecommendation(lambda: uow).execute(
        ReviewRecommendationInput(
            recommendation_id=recommendation.id,
            status="approved",
            comment="Ok para contato.",
            reviewed_by="Analista",
        )
    )

    assert view.review_status == "approved"
    assert view.review_comment == "Ok para contato."
    assert view.reviewed_by == "Analista"
    assert view.reviewed_at is not None
    assert uow.commits == 1
