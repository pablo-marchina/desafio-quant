"""Testes do contrato publico RecommendationGenerator."""

from uuid import uuid4

import pytest

from apps.api.src.modules.recommendations.application.dto import (
    GenerateRecommendationsInput,
    NvidiaTechnologySnapshot,
    StartupProfileSnapshot,
)
from apps.api.src.modules.recommendations.application.use_cases.generate_recommendations import (
    GenerateRecommendations,
)
from apps.api.src.modules.recommendations.tests.unit.test_generate_recommendations import (
    FakeCatalogSource,
    FakeProfileSource,
    FakeRecommendationRepository,
    FakeUoW,
)

NIM_SNAPSHOT = NvidiaTechnologySnapshot(
    slug="nvidia-nim",
    name="NVIDIA NIM",
    category="model_serving",
    use_cases=("servir LLMs em producao",),
    keywords=("llm", "generative ai", "inference", "api", "deployment", "microservice"),
)


@pytest.mark.anyio
async def test_generate_is_equivalent_to_execute() -> None:
    startup_id = uuid4()
    repository = FakeRecommendationRepository()
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(
        StartupProfileSnapshot(
            sector="LLM and generative AI",
            description="Provides inference API with simple deployment as microservice.",
            evidences=(),
        )
    )
    catalog_source = FakeCatalogSource([NIM_SNAPSHOT])

    generator = GenerateRecommendations(lambda: uow, profile_source, catalog_source)
    views = await generator.generate(startup_id)

    assert len(views) == 1
    assert views[0].technology_slug == "nvidia-nim"
    assert views[0].startup_id == startup_id


@pytest.mark.anyio
async def test_execute_delegates_to_generate() -> None:
    startup_id = uuid4()
    repository = FakeRecommendationRepository()
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(
        StartupProfileSnapshot(sector=None, description=None, evidences=())
    )
    catalog_source = FakeCatalogSource([NIM_SNAPSHOT])

    generator = GenerateRecommendations(lambda: uow, profile_source, catalog_source)
    views = await generator.execute(
        GenerateRecommendationsInput(startup_id=startup_id)
    )

    assert views == []
