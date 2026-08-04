"""Repositorio PostgreSQL para DiscoveryRun."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.startup_discovery.domain.entities import (
    DiscoveryRun,
    DiscoverySubmission,
)
from apps.api.src.modules.startup_discovery.domain.repositories import (
    DiscoveryRunRepository,
)
from apps.api.src.modules.startup_discovery.infrastructure.database.mappers.discovery_run_mapper import (
    DiscoveryRunMapper,
)
from apps.api.src.modules.startup_discovery.infrastructure.database.mappers.discovery_submission_mapper import (
    DiscoverySubmissionMapper,
)
from apps.api.src.modules.startup_discovery.infrastructure.database.models.discovery_run_model import (
    DiscoveryRunModel,
)
from apps.api.src.modules.startup_discovery.infrastructure.database.models.discovery_submission_model import (
    DiscoverySubmissionModel,
)


class PostgresDiscoveryRunRepository(DiscoveryRunRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, run: DiscoveryRun) -> None:
        model = await self._session.get(DiscoveryRunModel, run.id)
        if model is None:
            self._session.add(DiscoveryRunMapper.to_model(run))
        else:
            DiscoveryRunMapper.update_model(model, run)
        await self._session.flush()

    async def get_by_id(self, run_id: UUID) -> DiscoveryRun | None:
        model = await self._session.get(DiscoveryRunModel, run_id)
        if model is None:
            return None
        return DiscoveryRunMapper.to_entity(model)

    async def list_recent(self, *, limit: int = 20) -> list[DiscoveryRun]:
        statement = (
            select(DiscoveryRunModel)
            .order_by(DiscoveryRunModel.created_at.desc())
            .limit(limit)
        )
        models = (await self._session.scalars(statement)).all()
        return [DiscoveryRunMapper.to_entity(m) for m in models]

    async def save_submission(self, submission: DiscoverySubmission) -> None:
        model = await self._session.get(DiscoverySubmissionModel, submission.id)
        if model is None:
            self._session.add(DiscoverySubmissionMapper.to_model(submission))
        else:
            DiscoverySubmissionMapper.update_model(model, submission)
        await self._session.flush()

    async def list_submissions_for_run(
        self,
        run_id: UUID,
    ) -> list[DiscoverySubmission]:
        statement = (
            select(DiscoverySubmissionModel)
            .where(DiscoverySubmissionModel.run_id == run_id)
            .order_by(DiscoverySubmissionModel.submitted_at.asc())
        )
        models = (await self._session.scalars(statement)).all()
        return [DiscoverySubmissionMapper.to_entity(m) for m in models]
