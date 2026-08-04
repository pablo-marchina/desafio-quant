"""Caso de uso para registrar revisao humana de um briefing."""

from apps.api.src.modules.briefing.application.dto import (
    BriefingView,
    ReviewBriefingInput,
)
from apps.api.src.modules.briefing.application.unit_of_work import (
    BriefingsUnitOfWorkFactory,
)
from apps.api.src.modules.briefing.application.use_cases.generate_briefing import (
    to_briefing_view,
)
from apps.api.src.modules.briefing.domain.exceptions import BriefingNotFoundError


class ReviewBriefing:
    """Aprova/rejeita um briefing sem exigir auth completa."""

    def __init__(self, uow_factory: BriefingsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, review_input: ReviewBriefingInput) -> BriefingView:
        async with self._uow_factory() as uow:
            briefing = await uow.briefing_repository.get_by_id(
                review_input.briefing_id
            )
            if briefing is None:
                raise BriefingNotFoundError(
                    f"Briefing {review_input.briefing_id} nao encontrado."
                )

            briefing.review(
                status=review_input.status,
                comment=review_input.comment,
                reviewed_by=review_input.reviewed_by,
            )
            await uow.briefing_repository.update_review(briefing)
            await uow.commit()

        return to_briefing_view(briefing)
