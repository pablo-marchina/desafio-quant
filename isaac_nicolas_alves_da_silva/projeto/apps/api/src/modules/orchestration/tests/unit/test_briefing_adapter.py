"""Testes do adapter BriefingModulePort."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.api.src.modules.agents.application.dto import BriefingAgentResult
from apps.api.src.modules.briefing.application.dto import BriefingView
from apps.api.src.modules.briefing.domain.exceptions import (
    StartupProfileUnavailableError as BriefingStartupProfileUnavailableError,
)
from apps.api.src.modules.orchestration.domain.exceptions import (
    StartupProfileUnavailableError,
)
from apps.api.src.modules.orchestration.infrastructure.briefing_adapters.briefing_adapter import (
    BriefingModulePort,
)


class FakeGenerator:
    def __init__(self, view: BriefingView) -> None:
        self.view = view
        self.called = False

    async def generate(self, startup_id):
        self.called = True
        return self.view


class FailingGenerator:
    async def generate(self, startup_id):
        raise BriefingStartupProfileUnavailableError("sem perfil")


class FakeBriefingAgentService:
    def __init__(self, briefing_id, content: str = "prosa revisada") -> None:
        self.briefing_id = briefing_id
        self.content = content
        self.received_startup_id = None

    async def generate(self, briefing_input, *, thread_id=None):
        self.received_startup_id = briefing_input.startup_id
        return BriefingAgentResult(content=self.content, briefing_id=self.briefing_id)


class FailingBriefingAgentService:
    async def generate(self, briefing_input, *, thread_id=None):
        raise RuntimeError("llm indisponivel")


def _make_view(**overrides) -> BriefingView:
    defaults = dict(
        id=uuid4(),
        startup_id=uuid4(),
        content="conteudo deterministico",
        review_status="pending",
        review_comment=None,
        reviewed_by=None,
        reviewed_at=None,
        generated_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return BriefingView(**defaults)


@pytest.mark.anyio
async def test_uses_deterministic_generator_when_no_agent_service() -> None:
    view = _make_view()
    generator = FakeGenerator(view)
    port = BriefingModulePort(generator)

    briefing_id = await port.generate(uuid4())

    assert briefing_id == view.id
    assert generator.called is True


@pytest.mark.anyio
async def test_uses_agent_service_when_available_without_calling_generator() -> None:
    generator = FakeGenerator(_make_view())
    expected_id = uuid4()
    agent_service = FakeBriefingAgentService(expected_id)
    port = BriefingModulePort(generator, agent_service=agent_service)
    startup_id = uuid4()

    briefing_id = await port.generate(startup_id)

    assert briefing_id == expected_id
    assert generator.called is False
    assert agent_service.received_startup_id == startup_id


@pytest.mark.anyio
async def test_falls_back_to_deterministic_generator_when_agent_fails() -> None:
    view = _make_view()
    generator = FakeGenerator(view)
    port = BriefingModulePort(generator, agent_service=FailingBriefingAgentService())

    briefing_id = await port.generate(uuid4())

    assert briefing_id == view.id
    assert generator.called is True


@pytest.mark.anyio
async def test_translates_unavailable_profile_error_in_deterministic_path() -> None:
    port = BriefingModulePort(FailingGenerator())

    with pytest.raises(StartupProfileUnavailableError):
        await port.generate(uuid4())
