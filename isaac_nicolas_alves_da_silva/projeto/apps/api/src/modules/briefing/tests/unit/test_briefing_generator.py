"""Testes do contrato publico BriefingGenerator."""

from uuid import uuid4

import pytest

from apps.api.src.modules.briefing.application.dto import (
    GenerateBriefingInput,
    StartupProfileSnapshot,
)
from apps.api.src.modules.briefing.application.use_cases.generate_briefing import (
    GenerateBriefing,
)
from apps.api.src.modules.briefing.tests.unit.test_generate_briefing import (
    STARTUP_SNAPSHOT,
    FakeBriefingRepository,
    FakeProfileSource,
    FakeRecommendationsSource,
    FakeUoW,
)


@pytest.mark.anyio
async def test_generate_is_equivalent_to_execute() -> None:
    startup_id = uuid4()
    repository = FakeBriefingRepository()
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(
        StartupProfileSnapshot(startup=STARTUP_SNAPSHOT, evidences=())
    )
    recommendations_source = FakeRecommendationsSource([])

    generator = GenerateBriefing(lambda: uow, profile_source, recommendations_source)
    view = await generator.generate(startup_id)

    assert view.startup_id == startup_id
    assert "Acme AI" in view.content


@pytest.mark.anyio
async def test_execute_delegates_to_generate() -> None:
    startup_id = uuid4()
    repository = FakeBriefingRepository()
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(
        StartupProfileSnapshot(startup=STARTUP_SNAPSHOT, evidences=())
    )
    recommendations_source = FakeRecommendationsSource([])

    generator = GenerateBriefing(lambda: uow, profile_source, recommendations_source)
    view = await generator.execute(GenerateBriefingInput(startup_id=startup_id))

    assert view.startup_id == startup_id
