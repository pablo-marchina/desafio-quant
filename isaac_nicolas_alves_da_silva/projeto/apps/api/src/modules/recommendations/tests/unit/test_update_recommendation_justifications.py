"""Testes do caso de uso UpdateRecommendationJustifications."""

from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.recommendations.application.unit_of_work import (
    RecommendationsUnitOfWork,
)
from apps.api.src.modules.recommendations.application.use_cases.update_recommendation_justifications import (
    UpdateRecommendationJustifications,
)
from apps.api.src.modules.recommendations.domain.entities import Recommendation
from apps.api.src.modules.recommendations.domain.exceptions import RecommendationError
from apps.api.src.modules.recommendations.domain.repositories import (
    RecommendationRepository,
)


class FakeRecommendationRepository(RecommendationRepository):
    def __init__(self, items: list[Recommendation]) -> None:
        self.items: dict[UUID, Recommendation] = {item.id: item for item in items}

    async def save(self, recommendation: Recommendation) -> None:
        self.items[recommendation.id] = recommendation

    async def delete_by_startup_id(self, startup_id: UUID) -> None:
        self.items = {
            rec_id: rec
            for rec_id, rec in self.items.items()
            if rec.startup_id != startup_id
        }

    async def get_by_id(self, recommendation_id: UUID) -> Recommendation | None:
        return self.items.get(recommendation_id)

    async def list_by_startup_id(self, startup_id: UUID) -> list[Recommendation]:
        return [rec for rec in self.items.values() if rec.startup_id == startup_id]

    async def update_justification(
        self, recommendation_id: UUID, justification: str
    ) -> None:
        recommendation = self.items.get(recommendation_id)
        if recommendation is not None:
            recommendation.justification = justification

    async def update_review(self, recommendation: Recommendation) -> None:
        if recommendation.id in self.items:
            self.items[recommendation.id] = recommendation

    async def count_by_technology(self, *, limit: int = 10) -> list[tuple[str, str, int]]:
        return []


class FakeUoW(RecommendationsUnitOfWork):
    def __init__(self, repository: FakeRecommendationRepository) -> None:
        self.recommendation_repository = repository

    async def __aenter__(self) -> "FakeUoW":
        return self

    async def __aexit__(self, exception_type, exception, traceback) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _make_recommendation(startup_id: UUID, slug: str) -> Recommendation:
    return Recommendation(
        startup_id=startup_id,
        technology_slug=slug,
        technology_name=slug.upper(),
        category="inference",
        score=0.5,
        justification="justificativa original",
    )


@pytest.mark.anyio
async def test_updates_justification_for_matching_slug() -> None:
    startup_id = uuid4()
    recommendation = _make_recommendation(startup_id, "nim")
    repository = FakeRecommendationRepository([recommendation])
    use_case = UpdateRecommendationJustifications(lambda: FakeUoW(repository))

    await use_case.update_justifications(
        startup_id, {"nim": "justificativa revisada pelo agente"}
    )

    assert repository.items[recommendation.id].justification == (
        "justificativa revisada pelo agente"
    )


@pytest.mark.anyio
async def test_ignores_slugs_not_found_in_startup_recommendations() -> None:
    startup_id = uuid4()
    recommendation = _make_recommendation(startup_id, "nim")
    repository = FakeRecommendationRepository([recommendation])
    use_case = UpdateRecommendationJustifications(lambda: FakeUoW(repository))

    await use_case.update_justifications(
        startup_id, {"triton": "nunca deveria ser aplicado"}
    )

    assert repository.items[recommendation.id].justification == "justificativa original"


@pytest.mark.anyio
async def test_rejects_empty_justification() -> None:
    startup_id = uuid4()
    recommendation = _make_recommendation(startup_id, "nim")
    repository = FakeRecommendationRepository([recommendation])
    use_case = UpdateRecommendationJustifications(lambda: FakeUoW(repository))

    with pytest.raises(RecommendationError):
        await use_case.update_justifications(startup_id, {"nim": "   "})
