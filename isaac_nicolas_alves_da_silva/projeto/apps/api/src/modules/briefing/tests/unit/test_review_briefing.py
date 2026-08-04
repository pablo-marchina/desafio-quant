"""Testes do caso de uso ReviewBriefing."""

from uuid import uuid4

import pytest

from apps.api.src.modules.briefing.application.dto import ReviewBriefingInput
from apps.api.src.modules.briefing.application.use_cases.review_briefing import (
    ReviewBriefing,
)
from apps.api.src.modules.briefing.domain.entities import Briefing
from apps.api.src.modules.briefing.tests.unit.test_generate_briefing import (
    FakeBriefingRepository,
    FakeUoW,
)


@pytest.mark.anyio
async def test_review_briefing_rejects_with_comment() -> None:
    briefing = Briefing(startup_id=uuid4(), content="# Briefing")
    repository = FakeBriefingRepository()
    await repository.save(briefing)
    uow = FakeUoW(repository)

    view = await ReviewBriefing(lambda: uow).execute(
        ReviewBriefingInput(
            briefing_id=briefing.id,
            status="rejected",
            comment="Falta fonte sobre clientes.",
            reviewed_by="Analista",
        )
    )

    assert view.review_status == "rejected"
    assert view.review_comment == "Falta fonte sobre clientes."
    assert view.reviewed_by == "Analista"
    assert view.reviewed_at is not None
    assert uow.commits == 1
