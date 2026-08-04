"""Testes do caso de uso UpdateBriefingContent."""

from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.briefing.application.unit_of_work import BriefingsUnitOfWork
from apps.api.src.modules.briefing.application.use_cases.update_briefing_content import (
    UpdateBriefingContent,
)
from apps.api.src.modules.briefing.domain.entities import Briefing
from apps.api.src.modules.briefing.domain.exceptions import (
    BriefingError,
    BriefingNotFoundError,
)
from apps.api.src.modules.briefing.domain.repositories import BriefingRepository


class FakeBriefingRepository(BriefingRepository):
    def __init__(self, items: list[Briefing]) -> None:
        self.items: dict[UUID, Briefing] = {item.id: item for item in items}

    async def save(self, briefing: Briefing) -> None:
        self.items[briefing.id] = briefing

    async def delete_by_startup_id(self, startup_id: UUID) -> None:
        self.items = {
            briefing_id: briefing
            for briefing_id, briefing in self.items.items()
            if briefing.startup_id != startup_id
        }

    async def get_by_id(self, briefing_id: UUID) -> Briefing | None:
        return self.items.get(briefing_id)

    async def list_by_startup_id(self, startup_id: UUID) -> list[Briefing]:
        return sorted(
            (b for b in self.items.values() if b.startup_id == startup_id),
            key=lambda b: b.generated_at,
            reverse=True,
        )

    async def update_content(self, briefing_id: UUID, content: str) -> None:
        briefing = self.items.get(briefing_id)
        if briefing is not None:
            briefing.content = content

    async def update_review(self, briefing: Briefing) -> None:
        if briefing.id in self.items:
            self.items[briefing.id] = briefing


class FakeUoW(BriefingsUnitOfWork):
    def __init__(self, repository: FakeBriefingRepository) -> None:
        self.briefing_repository = repository

    async def __aenter__(self) -> "FakeUoW":
        return self

    async def __aexit__(self, exception_type, exception, traceback) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


@pytest.mark.anyio
async def test_updates_content_of_most_recent_briefing() -> None:
    startup_id = uuid4()
    briefing = Briefing(startup_id=startup_id, content="conteudo determinístico")
    repository = FakeBriefingRepository([briefing])
    use_case = UpdateBriefingContent(lambda: FakeUoW(repository))

    updated_id = await use_case.update_content(
        startup_id, "conteudo reescrito pelo agente"
    )

    assert updated_id == briefing.id
    assert repository.items[briefing.id].content == "conteudo reescrito pelo agente"


@pytest.mark.anyio
async def test_raises_when_no_briefing_exists_for_startup() -> None:
    use_case = UpdateBriefingContent(lambda: FakeUoW(FakeBriefingRepository([])))

    with pytest.raises(BriefingNotFoundError):
        await use_case.update_content(uuid4(), "conteudo novo")


@pytest.mark.anyio
async def test_rejects_empty_content() -> None:
    startup_id = uuid4()
    briefing = Briefing(startup_id=startup_id, content="conteudo determinístico")
    repository = FakeBriefingRepository([briefing])
    use_case = UpdateBriefingContent(lambda: FakeUoW(repository))

    with pytest.raises(BriefingError):
        await use_case.update_content(startup_id, "   ")
