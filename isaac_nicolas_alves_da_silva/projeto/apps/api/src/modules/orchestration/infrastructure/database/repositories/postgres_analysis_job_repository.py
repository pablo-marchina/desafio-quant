"""Repositorio PostgreSQL para AnalysisJob."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.orchestration.domain.entities import AnalysisJob
from apps.api.src.modules.orchestration.domain.repositories import (
    AnalysisJobRepository,
)
from apps.api.src.modules.orchestration.infrastructure.database.mappers.analysis_job_mapper import (
    AnalysisJobMapper,
)
from apps.api.src.modules.orchestration.infrastructure.database.models.analysis_job_model import (
    AnalysisJobModel,
)


class PostgresAnalysisJobRepository(AnalysisJobRepository):
    """Job de varias escritas: PENDING/RUNNING -> COMPLETED|FAILED na mesma linha."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, analysis_job: AnalysisJob) -> None:
        model = await self._session.get(AnalysisJobModel, analysis_job.id)
        if model is None:
            self._session.add(AnalysisJobMapper.to_model(analysis_job))
        else:
            AnalysisJobMapper.update_model(model, analysis_job)
        await self._session.flush()

    async def get_by_id(self, analysis_job_id: UUID) -> AnalysisJob | None:
        model = await self._session.get(AnalysisJobModel, analysis_job_id)
        if model is None:
            return None
        return AnalysisJobMapper.to_entity(model)

    async def list_by_startup_id(self, startup_id: UUID) -> list[AnalysisJob]:
        models = await self._session.scalars(
            select(AnalysisJobModel)
            .where(AnalysisJobModel.startup_id == startup_id)
            .order_by(AnalysisJobModel.created_at.desc())
        )
        return [AnalysisJobMapper.to_entity(model) for model in models]
