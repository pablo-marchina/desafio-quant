"""Testes do adapter RecommendationsModulePort."""

from uuid import uuid4

import pytest

from apps.api.src.modules.agents.application.dto import (
    RecommendationAgentResult,
    RecommendationCandidate,
)
from apps.api.src.modules.orchestration.domain.exceptions import (
    StartupProfileUnavailableError,
)
from apps.api.src.modules.orchestration.infrastructure.recommendations_adapters.recommendations_adapter import (
    RecommendationsModulePort,
)
from apps.api.src.modules.recommendations.application.dto import RecommendationView
from apps.api.src.modules.recommendations.domain.exceptions import (
    StartupProfileUnavailableError as RecommendationsStartupProfileUnavailableError,
)


class FakeGenerator:
    def __init__(self, views: list[RecommendationView]) -> None:
        self.views = views
        self.called = False

    async def generate(self, startup_id):
        self.called = True
        return self.views


class FailingGenerator:
    async def generate(self, startup_id):
        raise RecommendationsStartupProfileUnavailableError("sem perfil")


class FakeRecommendationAgentService:
    def __init__(self, candidates: list[RecommendationCandidate]) -> None:
        self.candidates = candidates
        self.received_startup_id = None

    async def recommend(self, recommendation_input, *, thread_id=None):
        self.received_startup_id = recommendation_input.startup_id
        return RecommendationAgentResult(recommendations=self.candidates)


def _make_view(**overrides) -> RecommendationView:
    defaults = dict(
        id=uuid4(),
        startup_id=uuid4(),
        technology_slug="nim",
        technology_name="NVIDIA NIM",
        category="inference",
        score=0.8,
        confidence=0.6,
        complexity="low",
        priority=1,
        justification="justificativa",
        matched_keywords=["llm"],
        evidence_ids=[],
        review_status="pending",
        review_comment=None,
        reviewed_by=None,
        reviewed_at=None,
        created_at=None,
    )
    defaults.update(overrides)
    return RecommendationView(**defaults)


def _make_candidate(**overrides) -> RecommendationCandidate:
    defaults = dict(
        technology_slug="nim",
        technology_name="NVIDIA NIM",
        category="inference",
        score=0.8,
        justification="justificativa revisada",
        matched_keywords=["llm"],
    )
    defaults.update(overrides)
    return RecommendationCandidate(**defaults)


@pytest.mark.anyio
async def test_uses_deterministic_generator_when_no_agent_service() -> None:
    generator = FakeGenerator([_make_view(), _make_view()])
    port = RecommendationsModulePort(generator)

    count = await port.generate(uuid4())

    assert count == 2
    assert generator.called is True


@pytest.mark.anyio
async def test_uses_agent_service_when_available_without_calling_generator() -> None:
    generator = FakeGenerator([_make_view()])
    agent_service = FakeRecommendationAgentService(
        [_make_candidate(), _make_candidate()]
    )
    port = RecommendationsModulePort(generator, agent_service=agent_service)
    startup_id = uuid4()

    count = await port.generate(startup_id)

    assert count == 2
    assert generator.called is False
    assert agent_service.received_startup_id == startup_id


@pytest.mark.anyio
async def test_translates_unavailable_profile_error_in_deterministic_path() -> None:
    port = RecommendationsModulePort(FailingGenerator())

    with pytest.raises(StartupProfileUnavailableError):
        await port.generate(uuid4())
