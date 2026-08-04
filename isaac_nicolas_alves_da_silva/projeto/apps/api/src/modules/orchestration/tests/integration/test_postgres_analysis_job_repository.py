"""Testes integrados do repositorio de orchestration contra PostgreSQL."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.database.relational.session import engine
from apps.api.src.modules.orchestration.domain.entities import AnalysisJob
from apps.api.src.modules.orchestration.domain.enums import AnalysisJobStatus
from apps.api.src.modules.orchestration.infrastructure.database.repositories.postgres_analysis_job_repository import (
    PostgresAnalysisJobRepository,
)
from apps.api.src.modules.startups.domain.entities import Startup
from apps.api.src.modules.startups.infrastructure.database.repositories.postgres_startup_repository import (
    PostgresStartupRepository,
)


@pytest.mark.anyio
async def test_postgres_repository_persists_and_updates_job_status() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)

        try:
            startup_repo = PostgresStartupRepository(session)
            startup = Startup(name="Startup Example", sector="LLM customer service")
            await startup_repo.save(startup)

            analysis_repo = PostgresAnalysisJobRepository(session)
            job = AnalysisJob(startup_id=startup.id)
            job.start()
            await analysis_repo.save(job)

            restored = await analysis_repo.get_by_id(job.id)
            assert restored is not None
            assert restored.status is AnalysisJobStatus.RUNNING

            job.complete(recommendation_count=2, briefing_id=uuid4())
            await analysis_repo.save(job)

            updated = await analysis_repo.get_by_id(job.id)
            assert updated is not None
            assert updated.status is AnalysisJobStatus.COMPLETED
            assert updated.recommendation_count == 2

            listed = await analysis_repo.list_by_startup_id(startup.id)
            assert len(listed) == 1
        finally:
            await session.close()
            await transaction.rollback()

    await engine.dispose()
