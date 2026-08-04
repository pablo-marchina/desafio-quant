"""Testes integrados do repositorio de briefing contra PostgreSQL."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.database.relational.session import engine
from apps.api.src.modules.briefing.domain.entities import Briefing
from apps.api.src.modules.briefing.infrastructure.database.repositories.postgres_briefing_repository import (
    PostgresBriefingRepository,
)
from apps.api.src.modules.startups.domain.entities import Startup
from apps.api.src.modules.startups.infrastructure.database.repositories.postgres_startup_repository import (
    PostgresStartupRepository,
)


@pytest.mark.anyio
async def test_postgres_repository_persists_and_replaces_briefing() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)

        try:
            startup_repo = PostgresStartupRepository(session)
            startup = Startup(name="Startup Example", sector="LLM customer service")
            await startup_repo.save(startup)

            briefing_repo = PostgresBriefingRepository(session)
            briefing = Briefing(
                startup_id=startup.id,
                content="# Briefing Executivo — Startup Example\n\nConteudo de teste.",
            )
            await briefing_repo.save(briefing)

            restored = await briefing_repo.get_by_id(briefing.id)
            assert restored is not None
            assert "Startup Example" in restored.content

            listed = await briefing_repo.list_by_startup_id(startup.id)
            assert len(listed) == 1

            await briefing_repo.delete_by_startup_id(startup.id)
            listed_after_delete = await briefing_repo.list_by_startup_id(startup.id)
            assert listed_after_delete == []
        finally:
            await session.close()
            await transaction.rollback()

    await engine.dispose()
