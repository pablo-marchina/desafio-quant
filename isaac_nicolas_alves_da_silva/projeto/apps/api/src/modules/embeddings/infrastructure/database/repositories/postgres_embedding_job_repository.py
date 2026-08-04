"""Repositorio PostgreSQL para EmbeddingJob."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.embeddings.domain.entities import EmbeddingJob
from apps.api.src.modules.embeddings.domain.repositories import EmbeddingJobRepository
from apps.api.src.modules.embeddings.infrastructure.database.mappers.embedding_job_mapper import (
    EmbeddingJobMapper,
)
from apps.api.src.modules.embeddings.infrastructure.database.models.embedding_job_model import (
    EmbeddingJobModel,
)


class PostgresEmbeddingJobRepository(EmbeddingJobRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, job: EmbeddingJob) -> None:
        model = await self._session.get(EmbeddingJobModel, job.id)
        if model is None:
            self._session.add(EmbeddingJobMapper.to_model(job))
        else:
            EmbeddingJobMapper.update_model(model, job)
        await self._session.flush()

    async def get_by_id(self, job_id: UUID) -> EmbeddingJob | None:
        model = await self._session.get(EmbeddingJobModel, job_id)
        if model is None:
            return None
        return EmbeddingJobMapper.to_entity(model)
