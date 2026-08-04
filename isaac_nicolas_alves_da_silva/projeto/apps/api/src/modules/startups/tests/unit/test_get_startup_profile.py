"""Testes do contrato publico StartupProfileReader."""

from uuid import uuid4

import pytest

from apps.api.src.modules.startups.application.use_cases.get_startup_profile import (
    GetStartupProfile,
)
from apps.api.src.modules.startups.domain.entities import Startup, StartupEvidence
from apps.api.src.modules.startups.domain.enums import StartupEvidenceType
from apps.api.src.modules.startups.domain.exceptions import StartupNotFoundError
from apps.api.src.modules.startups.tests.unit.test_startup_use_cases import (
    FakeEvidenceRepository,
    FakeStartupRepository,
    FakeUoW,
)


def _make_uow() -> FakeUoW:
    return FakeUoW(FakeStartupRepository(), FakeEvidenceRepository())


@pytest.mark.anyio
async def test_get_profile_returns_startup_and_evidences() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI", sector="LLM customer service")
    await uow.startup_repository.save(startup)
    evidence = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://example.com/news",
        evidence_type=StartupEvidenceType.NEWS,
        title="Acme launches LLM chatbot",
    )
    await uow.evidence_repository.save(evidence)

    profile = await GetStartupProfile(lambda: uow).get_profile(startup.id)

    assert profile.startup.id == startup.id
    assert len(profile.evidences) == 1
    assert profile.evidences[0].id == evidence.id


@pytest.mark.anyio
async def test_get_profile_raises_when_startup_missing() -> None:
    uow = _make_uow()

    with pytest.raises(StartupNotFoundError):
        await GetStartupProfile(lambda: uow).get_profile(uuid4())
