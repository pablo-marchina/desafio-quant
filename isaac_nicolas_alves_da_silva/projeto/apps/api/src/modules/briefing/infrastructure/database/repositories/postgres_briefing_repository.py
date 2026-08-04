"""Repositorio PostgreSQL para Briefing."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.briefing.domain.entities import Briefing
from apps.api.src.modules.briefing.domain.repositories import BriefingRepository
from apps.api.src.modules.briefing.infrastructure.database.mappers.briefing_mapper import (
    BriefingMapper,
)
from apps.api.src.modules.briefing.infrastructure.database.models.briefing_model import (
    BriefingModel,
)


class PostgresBriefingRepository(BriefingRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, briefing: Briefing) -> None:
        self._session.add(BriefingMapper.to_model(briefing))
        await self._session.flush()

    async def delete_by_startup_id(self, startup_id: UUID) -> None:
        await self._session.execute(
            delete(BriefingModel).where(BriefingModel.startup_id == startup_id)
        )
        await self._session.flush()

    async def get_by_id(self, briefing_id: UUID) -> Briefing | None:
        model = await self._session.get(BriefingModel, briefing_id)
        if model is None:
            return None
        return BriefingMapper.to_entity(model)

    async def list_by_startup_id(self, startup_id: UUID) -> list[Briefing]:
        models = await self._session.scalars(
            select(BriefingModel)
            .where(BriefingModel.startup_id == startup_id)
            .order_by(BriefingModel.generated_at.desc())
        )
        return [BriefingMapper.to_entity(model) for model in models]

    async def update_content(self, briefing_id: UUID, content: str) -> None:
        model = await self._session.get(BriefingModel, briefing_id)
        if model is None:
            return
        model.content = content
        await self._session.flush()

    async def update_review(self, briefing: Briefing) -> None:
        model = await self._session.get(BriefingModel, briefing.id)
        if model is None:
            return
        model.review_status = briefing.review_status
        model.review_comment = briefing.review_comment
        model.reviewed_by = briefing.reviewed_by
        model.reviewed_at = briefing.reviewed_at
        await self._session.flush()
