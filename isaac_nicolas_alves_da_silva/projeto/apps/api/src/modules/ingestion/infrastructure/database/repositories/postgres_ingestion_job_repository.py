"""Repositorio PostgreSQL para IngestionJob."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.ingestion.domain.entities import IngestionJob
from apps.api.src.modules.ingestion.domain.repositories import IngestionJobRepository
from apps.api.src.modules.ingestion.infrastructure.database.mappers.ingestion_job_mapper import (
    IngestionJobMapper,
)
from apps.api.src.modules.ingestion.infrastructure.database.models.ingestion_job_model import (
    IngestionJobModel,
)


class PostgresIngestionJobRepository(IngestionJobRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, job: IngestionJob) -> None:
        model = await self._session.get(IngestionJobModel, job.id)
        if model is None:
            self._session.add(IngestionJobMapper.to_model(job))
        else:
            IngestionJobMapper.update_model(model, job)
        await self._session.flush()

    async def get_by_id(self, job_id: UUID) -> IngestionJob | None:
        model = await self._session.get(IngestionJobModel, job_id)
        if model is None:
            return None
        return IngestionJobMapper.to_entity(model)

    async def get_by_scraping_result_id(
        self, scraping_result_id: UUID
    ) -> IngestionJob | None:
        model = await self._session.scalar(
            select(IngestionJobModel).where(
                IngestionJobModel.scraping_result_id == scraping_result_id
            )
        )
        if model is None:
            return None
        return IngestionJobMapper.to_entity(model)
