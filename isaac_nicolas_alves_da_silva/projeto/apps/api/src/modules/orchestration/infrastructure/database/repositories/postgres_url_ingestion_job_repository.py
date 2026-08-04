"""Repositorio PostgreSQL para UrlIngestionJob."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.orchestration.domain.entities import UrlIngestionJob
from apps.api.src.modules.orchestration.domain.enums import UrlIngestionJobStatus
from apps.api.src.modules.orchestration.domain.repositories import (
    UrlIngestionJobRepository,
)
from apps.api.src.modules.orchestration.infrastructure.database.mappers.url_ingestion_job_mapper import (
    UrlIngestionJobMapper,
)
from apps.api.src.modules.orchestration.infrastructure.database.models.url_ingestion_job_model import (
    UrlIngestionJobModel,
)


class PostgresUrlIngestionJobRepository(UrlIngestionJobRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, job: UrlIngestionJob) -> None:
        model = await self._session.get(UrlIngestionJobModel, job.id)
        if model is None:
            self._session.add(UrlIngestionJobMapper.to_model(job))
        else:
            UrlIngestionJobMapper.update_model(model, job)
        await self._session.flush()

    async def get_by_id(self, job_id: UUID) -> UrlIngestionJob | None:
        model = await self._session.get(UrlIngestionJobModel, job_id)
        if model is None:
            return None
        return UrlIngestionJobMapper.to_entity(model)

    async def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: UrlIngestionJobStatus | None = None,
        source_type: str | None = None,
    ) -> tuple[list[UrlIngestionJob], int]:
        filters = []
        if status is not None:
            filters.append(UrlIngestionJobModel.status == status.value)
        if source_type:
            filters.append(UrlIngestionJobModel.source_type == source_type.strip())

        statement = (
            select(UrlIngestionJobModel)
            .where(*filters)
            .order_by(UrlIngestionJobModel.created_at.desc(), UrlIngestionJobModel.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        count_statement = (
            select(func.count()).select_from(UrlIngestionJobModel).where(*filters)
        )
        models = (await self._session.scalars(statement)).all()
        total = await self._session.scalar(count_statement)
        return [UrlIngestionJobMapper.to_entity(model) for model in models], total or 0

    async def list_completed_by_url(self, url: str) -> list[UrlIngestionJob]:
        statement = (
            select(UrlIngestionJobModel)
            .where(
                UrlIngestionJobModel.url == url,
                UrlIngestionJobModel.status == UrlIngestionJobStatus.COMPLETED.value,
            )
            .order_by(UrlIngestionJobModel.created_at.desc())
        )
        models = (await self._session.scalars(statement)).all()
        return [UrlIngestionJobMapper.to_entity(model) for model in models]

    async def list_by_startup_id(self, startup_id: UUID) -> list[UrlIngestionJob]:
        statement = (
            select(UrlIngestionJobModel)
            .where(UrlIngestionJobModel.startup_id == startup_id)
            .order_by(UrlIngestionJobModel.created_at.desc(), UrlIngestionJobModel.id.desc())
        )
        models = (await self._session.scalars(statement)).all()
        return [UrlIngestionJobMapper.to_entity(model) for model in models]
