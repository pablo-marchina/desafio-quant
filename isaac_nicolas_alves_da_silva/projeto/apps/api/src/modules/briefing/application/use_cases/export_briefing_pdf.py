"""Caso de uso para exportar um briefing existente como PDF."""

from dataclasses import dataclass
from uuid import UUID

from apps.api.src.modules.briefing.application.ports import BriefingDocumentRenderer
from apps.api.src.modules.briefing.application.unit_of_work import (
    BriefingsUnitOfWorkFactory,
)
from apps.api.src.modules.briefing.application.use_cases.generate_briefing import (
    to_briefing_view,
)
from apps.api.src.modules.briefing.domain.exceptions import BriefingNotFoundError


@dataclass(frozen=True)
class BriefingPdfView:
    filename: str
    content: bytes


class ExportBriefingPdf:
    """Busca o briefing por id e devolve seu conteudo renderizado em PDF."""

    def __init__(
        self,
        uow_factory: BriefingsUnitOfWorkFactory,
        renderer: BriefingDocumentRenderer,
    ) -> None:
        self._uow_factory = uow_factory
        self._renderer = renderer

    async def execute(self, *, briefing_id: UUID) -> BriefingPdfView:
        async with self._uow_factory() as uow:
            briefing = await uow.briefing_repository.get_by_id(briefing_id)

        if briefing is None:
            raise BriefingNotFoundError(f"Briefing {briefing_id} nao encontrado.")

        view = to_briefing_view(briefing)
        pdf_bytes = await self._renderer.render_pdf(view)
        return BriefingPdfView(
            filename=f"briefing-{view.startup_id}.pdf",
            content=pdf_bytes,
        )
