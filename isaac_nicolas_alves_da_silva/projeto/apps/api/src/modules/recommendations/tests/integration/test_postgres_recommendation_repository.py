"""Testes integrados do repositorio de recommendations contra PostgreSQL."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.database.relational.session import engine
from apps.api.src.modules.recommendations.domain.entities import Recommendation
from apps.api.src.modules.recommendations.infrastructure.database.repositories.postgres_recommendation_repository import (
    PostgresRecommendationRepository,
)
from apps.api.src.modules.startups.domain.entities import Startup
from apps.api.src.modules.startups.infrastructure.database.repositories.postgres_startup_repository import (
    PostgresStartupRepository,
)


@pytest.mark.anyio
async def test_postgres_repository_persists_and_replaces_recommendations() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)

        try:
            startup_repo = PostgresStartupRepository(session)
            startup = Startup(name="Startup Example", sector="LLM customer service")
            await startup_repo.save(startup)

            recommendation_repo = PostgresRecommendationRepository(session)
            evidence_id = uuid4()
            recommendation = Recommendation(
                startup_id=startup.id,
                technology_slug="nvidia-nim",
                technology_name="NVIDIA NIM",
                category="model_serving",
                score=1.0,
                justification="Evidencias mencionam llm e inference.",
                matched_keywords=("llm", "inference"),
                evidence_ids=(evidence_id,),
            )
            await recommendation_repo.save(recommendation)

            restored = await recommendation_repo.get_by_id(recommendation.id)
            assert restored is not None
            assert restored.technology_slug == "nvidia-nim"
            assert restored.matched_keywords == ("llm", "inference")
            assert restored.evidence_ids == (evidence_id,)

            listed = await recommendation_repo.list_by_startup_id(startup.id)
            assert len(listed) == 1

            await recommendation_repo.delete_by_startup_id(startup.id)
            listed_after_delete = await recommendation_repo.list_by_startup_id(
                startup.id
            )
            assert listed_after_delete == []
        finally:
            await session.close()
            await transaction.rollback()

    await engine.dispose()
