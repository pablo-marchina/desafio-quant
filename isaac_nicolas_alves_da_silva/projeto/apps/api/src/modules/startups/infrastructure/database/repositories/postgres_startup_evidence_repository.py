"""Repositorio PostgreSQL para StartupEvidence."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.startups.domain.entities import StartupEvidence
from apps.api.src.modules.startups.domain.repositories import (
    StartupEvidenceRepository,
)
from apps.api.src.modules.startups.infrastructure.database.mappers.startup_evidence_mapper import (
    StartupEvidenceMapper,
)
from apps.api.src.modules.startups.infrastructure.database.models.startup_evidence_model import (
    StartupEvidenceModel,
)


class PostgresStartupEvidenceRepository(StartupEvidenceRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, evidence: StartupEvidence) -> None:
        model = await self._session.get(StartupEvidenceModel, evidence.id)
        if model is None:
            self._session.add(StartupEvidenceMapper.to_model(evidence))
        else:
            StartupEvidenceMapper.update_model(model, evidence)
        await self._session.flush()

    async def get_by_id(self, evidence_id: UUID) -> StartupEvidence | None:
        model = await self._session.get(StartupEvidenceModel, evidence_id)
        if model is None:
            return None
        return StartupEvidenceMapper.to_entity(model)

    async def list_by_startup_id(self, startup_id: UUID) -> list[StartupEvidence]:
        models = await self._session.scalars(
            select(StartupEvidenceModel)
            .where(StartupEvidenceModel.startup_id == startup_id)
            .order_by(StartupEvidenceModel.created_at)
        )
        return [StartupEvidenceMapper.to_entity(model) for model in models]
