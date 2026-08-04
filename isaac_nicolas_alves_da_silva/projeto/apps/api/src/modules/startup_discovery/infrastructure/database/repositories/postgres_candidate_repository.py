"""Repositorio PostgreSQL para StartupDiscoveryCandidate."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.startup_discovery.domain.entities import (
    StartupDiscoveryCandidate,
)
from apps.api.src.modules.startup_discovery.domain.enums import CandidateStatus
from apps.api.src.modules.startup_discovery.domain.repositories import (
    CandidateRepository,
)
from apps.api.src.modules.startup_discovery.infrastructure.database.mappers.discovery_candidate_mapper import (
    DiscoveryCandidateMapper,
)
from apps.api.src.modules.startup_discovery.infrastructure.database.models.discovery_candidate_model import (
    DiscoveryCandidateModel,
)


class PostgresCandidateRepository(CandidateRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, candidate: StartupDiscoveryCandidate) -> None:
        model = await self._session.get(DiscoveryCandidateModel, candidate.id)
        if model is None:
            self._session.add(DiscoveryCandidateMapper.to_model(candidate))
        else:
            DiscoveryCandidateMapper.update_model(model, candidate)
        await self._session.flush()

    async def get_by_id(self, candidate_id: UUID) -> StartupDiscoveryCandidate | None:
        model = await self._session.get(DiscoveryCandidateModel, candidate_id)
        if model is None:
            return None
        return DiscoveryCandidateMapper.to_entity(model)

    async def list_by_run_id(self, run_id: UUID) -> list[StartupDiscoveryCandidate]:
        statement = (
            select(DiscoveryCandidateModel)
            .where(DiscoveryCandidateModel.run_id == run_id)
            .order_by(DiscoveryCandidateModel.rank.asc().nulls_last())
        )
        models = (await self._session.scalars(statement)).all()
        return [DiscoveryCandidateMapper.to_entity(m) for m in models]

    async def list_by_status(
        self,
        status: CandidateStatus,
        *,
        limit: int = 100,
    ) -> list[StartupDiscoveryCandidate]:
        statement = (
            select(DiscoveryCandidateModel)
            .where(DiscoveryCandidateModel.status == status.value)
            .order_by(DiscoveryCandidateModel.created_at.desc())
            .limit(limit)
        )
        models = (await self._session.scalars(statement)).all()
        return [DiscoveryCandidateMapper.to_entity(m) for m in models]
