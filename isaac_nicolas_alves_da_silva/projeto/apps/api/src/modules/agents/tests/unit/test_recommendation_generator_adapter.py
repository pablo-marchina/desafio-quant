"""Testes do adapter RecommendationGeneratorAdapter."""

from uuid import uuid4

import pytest

from apps.api.src.modules.agents.domain.exceptions import AgentRecommendationError
from apps.api.src.modules.agents.infrastructure.recommendations_adapters.recommendation_generator_adapter import (
    RecommendationGeneratorAdapter,
)
from apps.api.src.modules.recommendations.application.dto import RecommendationView
from apps.api.src.modules.recommendations.domain.exceptions import (
    StartupProfileUnavailableError,
)


class FakeRecommendationGenerator:
    def __init__(self, views: list[RecommendationView]) -> None:
        self.views = views
        self.last_startup_id = None

    async def generate(self, startup_id):
        self.last_startup_id = startup_id
        return self.views


class FailingRecommendationGenerator:
    async def generate(self, startup_id):
        raise StartupProfileUnavailableError("Startup nao encontrada.")


class FakeJustificationUpdater:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def update_justifications(self, startup_id, justifications):
        self.calls.append((startup_id, justifications))


class FailingJustificationUpdater:
    async def update_justifications(self, startup_id, justifications):
        raise StartupProfileUnavailableError("Startup nao encontrada.")


def make_view(**overrides) -> RecommendationView:
    defaults = dict(
        id=uuid4(),
        startup_id=uuid4(),
        technology_slug="nvidia-nim",
        technology_name="NVIDIA NIM",
        category="inference",
        score=0.8,
        confidence=0.6,
        complexity="low",
        priority=1,
        justification="Evidencias mencionam: llm, inference. NVIDIA NIM e indicada para: model serving.",
        matched_keywords=["llm", "inference"],
        evidence_ids=[],
        review_status="pending",
        review_comment=None,
        reviewed_by=None,
        reviewed_at=None,
        created_at=None,
    )
    defaults.update(overrides)
    return RecommendationView(**defaults)


@pytest.mark.anyio
async def test_generate_maps_views_to_candidates() -> None:
    startup_id = uuid4()
    view = make_view()
    adapter = RecommendationGeneratorAdapter(
        FakeRecommendationGenerator([view]), FakeJustificationUpdater()
    )

    candidates = await adapter.generate(startup_id)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.technology_slug == "nvidia-nim"
    assert candidate.technology_name == "NVIDIA NIM"
    assert candidate.score == 0.8
    assert candidate.matched_keywords == ["llm", "inference"]


@pytest.mark.anyio
async def test_generate_translates_recommendation_error() -> None:
    adapter = RecommendationGeneratorAdapter(
        FailingRecommendationGenerator(), FakeJustificationUpdater()
    )

    with pytest.raises(AgentRecommendationError):
        await adapter.generate(uuid4())


@pytest.mark.anyio
async def test_update_justifications_delegates_to_updater() -> None:
    startup_id = uuid4()
    updater = FakeJustificationUpdater()
    adapter = RecommendationGeneratorAdapter(
        FakeRecommendationGenerator([]), updater
    )

    await adapter.update_justifications(startup_id, {"nvidia-nim": "nova justificativa"})

    assert updater.calls == [(startup_id, {"nvidia-nim": "nova justificativa"})]


@pytest.mark.anyio
async def test_update_justifications_translates_recommendation_error() -> None:
    adapter = RecommendationGeneratorAdapter(
        FakeRecommendationGenerator([]), FailingJustificationUpdater()
    )

    with pytest.raises(AgentRecommendationError):
        await adapter.update_justifications(uuid4(), {})
