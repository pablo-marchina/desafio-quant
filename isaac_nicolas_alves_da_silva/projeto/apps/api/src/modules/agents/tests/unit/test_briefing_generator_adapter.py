"""Testes do adapter BriefingGeneratorAdapter."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.api.src.modules.agents.domain.exceptions import AgentBriefingError
from apps.api.src.modules.agents.infrastructure.briefing_adapters.briefing_generator_adapter import (
    BriefingGeneratorAdapter,
)
from apps.api.src.modules.briefing.application.dto import BriefingView
from apps.api.src.modules.briefing.domain.exceptions import (
    StartupProfileUnavailableError,
)


class FakeBriefingGenerator:
    def __init__(self, view: BriefingView) -> None:
        self.view = view
        self.last_startup_id = None

    async def generate(self, startup_id):
        self.last_startup_id = startup_id
        return self.view


class FailingBriefingGenerator:
    async def generate(self, startup_id):
        raise StartupProfileUnavailableError("Startup nao encontrada.")


class FakeContentUpdater:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.briefing_id = uuid4()

    async def update_content(self, startup_id, content):
        self.calls.append((startup_id, content))
        return self.briefing_id


class FailingContentUpdater:
    async def update_content(self, startup_id, content):
        raise StartupProfileUnavailableError("Startup nao encontrada.")


@pytest.mark.anyio
async def test_generate_returns_content() -> None:
    startup_id = uuid4()
    view = BriefingView(
        id=uuid4(),
        startup_id=startup_id,
        content="# Briefing Executivo — Acme AI\n",
        review_status="pending",
        review_comment=None,
        reviewed_by=None,
        reviewed_at=None,
        generated_at=datetime.now(UTC),
    )
    adapter = BriefingGeneratorAdapter(FakeBriefingGenerator(view), FakeContentUpdater())

    content = await adapter.generate(startup_id)

    assert content == "# Briefing Executivo — Acme AI\n"


@pytest.mark.anyio
async def test_generate_translates_briefing_error() -> None:
    adapter = BriefingGeneratorAdapter(FailingBriefingGenerator(), FakeContentUpdater())

    with pytest.raises(AgentBriefingError):
        await adapter.generate(uuid4())


@pytest.mark.anyio
async def test_update_content_delegates_to_updater() -> None:
    startup_id = uuid4()
    updater = FakeContentUpdater()
    view = BriefingView(
        id=uuid4(),
        startup_id=startup_id,
        content="x",
        review_status="pending",
        review_comment=None,
        reviewed_by=None,
        reviewed_at=None,
        generated_at=datetime.now(UTC),
    )
    adapter = BriefingGeneratorAdapter(FakeBriefingGenerator(view), updater)

    returned_id = await adapter.update_content(startup_id, "prosa reescrita")

    assert updater.calls == [(startup_id, "prosa reescrita")]
    assert returned_id == updater.briefing_id


@pytest.mark.anyio
async def test_update_content_translates_briefing_error() -> None:
    view = BriefingView(
        id=uuid4(),
        startup_id=uuid4(),
        content="x",
        review_status="pending",
        review_comment=None,
        reviewed_by=None,
        reviewed_at=None,
        generated_at=datetime.now(UTC),
    )
    adapter = BriefingGeneratorAdapter(FakeBriefingGenerator(view), FailingContentUpdater())

    with pytest.raises(AgentBriefingError):
        await adapter.update_content(uuid4(), "conteudo")
