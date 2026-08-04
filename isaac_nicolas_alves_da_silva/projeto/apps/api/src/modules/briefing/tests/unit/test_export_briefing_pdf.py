"""Testes do caso de uso ExportBriefingPdf."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.briefing.application.dto import BriefingView
from apps.api.src.modules.briefing.application.ports import BriefingDocumentRenderer
from apps.api.src.modules.briefing.application.unit_of_work import BriefingsUnitOfWork
from apps.api.src.modules.briefing.application.use_cases.export_briefing_pdf import (
    ExportBriefingPdf,
)
from apps.api.src.modules.briefing.domain.entities import Briefing
from apps.api.src.modules.briefing.domain.exceptions import (
    BriefingNotFoundError,
    BriefingRenderingError,
)
from apps.api.src.modules.briefing.domain.repositories import BriefingRepository


class FakeBriefingRepository(BriefingRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, Briefing] = {}

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
        return [b for b in self.items.values() if b.startup_id == startup_id]

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

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


class FakeRenderer(BriefingDocumentRenderer):
    def __init__(self, *, content: bytes | None = b"%PDF-fake", error: Exception | None = None) -> None:
        self._content = content
        self._error = error
        self.calls: list[BriefingView] = []

    async def render_pdf(self, briefing: BriefingView) -> bytes:
        self.calls.append(briefing)
        if self._error is not None:
            raise self._error
        assert self._content is not None
        return self._content


@pytest.mark.anyio
async def test_export_briefing_pdf_returns_filename_and_bytes() -> None:
    repository = FakeBriefingRepository()
    startup_id = uuid4()
    briefing = Briefing(startup_id=startup_id, content="# Resumo\n\nConteudo.")
    await repository.save(briefing)
    renderer = FakeRenderer(content=b"%PDF-1.7 fake bytes")

    use_case = ExportBriefingPdf(lambda: FakeUoW(repository), renderer)
    result = await use_case.execute(briefing_id=briefing.id)

    assert result.filename == f"briefing-{startup_id}.pdf"
    assert result.content == b"%PDF-1.7 fake bytes"
    assert renderer.calls[0].id == briefing.id


@pytest.mark.anyio
async def test_export_briefing_pdf_raises_not_found_for_missing_briefing() -> None:
    repository = FakeBriefingRepository()
    use_case = ExportBriefingPdf(lambda: FakeUoW(repository), FakeRenderer())

    with pytest.raises(BriefingNotFoundError):
        await use_case.execute(briefing_id=uuid4())


@pytest.mark.anyio
async def test_export_briefing_pdf_propagates_renderer_error() -> None:
    repository = FakeBriefingRepository()
    briefing = Briefing(startup_id=uuid4(), content="# Resumo")
    await repository.save(briefing)
    renderer = FakeRenderer(error=BriefingRenderingError("falha no chromium"))

    use_case = ExportBriefingPdf(lambda: FakeUoW(repository), renderer)

    with pytest.raises(BriefingRenderingError):
        await use_case.execute(briefing_id=briefing.id)
