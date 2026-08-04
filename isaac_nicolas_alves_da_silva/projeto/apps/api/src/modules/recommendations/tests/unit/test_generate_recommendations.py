"""Testes do caso de uso GenerateRecommendations."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.recommendations.application.dto import (
    AIProfileSnapshot,
    EvidenceSnapshot,
    GenerateRecommendationsInput,
    GroundedJustification,
    NvidiaTechnologySnapshot,
    StartupProfileSnapshot,
)
from apps.api.src.modules.recommendations.application.ports import (
    NvidiaCatalogSource,
    NvidiaKnowledgeGrounder,
    NvidiaSemanticCandidateSelector,
    StartupProfileSource,
)
from apps.api.src.modules.recommendations.application.unit_of_work import (
    RecommendationsUnitOfWork,
)
from apps.api.src.modules.recommendations.application.use_cases.generate_recommendations import (
    GenerateRecommendations,
)
from apps.api.src.modules.recommendations.domain.entities import Recommendation
from apps.api.src.modules.recommendations.domain.exceptions import (
    StartupProfileUnavailableError,
)
from apps.api.src.modules.recommendations.domain.repositories import (
    RecommendationRepository,
)

NIM_SNAPSHOT = NvidiaTechnologySnapshot(
    slug="nvidia-nim",
    name="NVIDIA NIM",
    category="model_serving",
    use_cases=("servir LLMs em producao",),
    keywords=("llm", "generative ai", "inference", "api", "deployment", "microservice"),
)
RAPIDS_SNAPSHOT = NvidiaTechnologySnapshot(
    slug="rapids",
    name="RAPIDS",
    category="data_science",
    use_cases=("processar grandes volumes tabulares",),
    keywords=("data science", "analytics", "dataframe", "gpu", "pandas", "spark"),
    complexity="medium",
    supported_workloads={"analytics": 0.95},
)


class FakeProfileSource(StartupProfileSource):
    def __init__(self, profile: StartupProfileSnapshot | None) -> None:
        self._profile = profile

    async def get_profile(self, startup_id: UUID) -> StartupProfileSnapshot:
        if self._profile is None:
            raise StartupProfileUnavailableError(f"Startup {startup_id} nao encontrada.")
        return self._profile


class FakeCatalogSource(NvidiaCatalogSource):
    def __init__(self, technologies: list[NvidiaTechnologySnapshot]) -> None:
        self._technologies = technologies

    async def list_technologies(self) -> list[NvidiaTechnologySnapshot]:
        return self._technologies


class FakeRecommendationRepository(RecommendationRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, Recommendation] = {}
        self.deleted_for_startup: list[UUID] = []

    async def save(self, recommendation: Recommendation) -> None:
        self.items[recommendation.id] = recommendation

    async def delete_by_startup_id(self, startup_id: UUID) -> None:
        self.deleted_for_startup.append(startup_id)
        self.items = {
            rec_id: rec
            for rec_id, rec in self.items.items()
            if rec.startup_id != startup_id
        }

    async def get_by_id(self, recommendation_id: UUID) -> Recommendation | None:
        return self.items.get(recommendation_id)

    async def list_by_startup_id(self, startup_id: UUID) -> list[Recommendation]:
        return [rec for rec in self.items.values() if rec.startup_id == startup_id]

    async def update_justification(
        self, recommendation_id: UUID, justification: str
    ) -> None:
        recommendation = self.items.get(recommendation_id)
        if recommendation is not None:
            recommendation.justification = justification

    async def update_review(self, recommendation: Recommendation) -> None:
        if recommendation.id in self.items:
            self.items[recommendation.id] = recommendation

    async def count_by_technology(self, *, limit: int = 10) -> list[tuple[str, str, int]]:
        return []


class FakeGrounder(NvidiaKnowledgeGrounder):
    def __init__(self, result: GroundedJustification | None) -> None:
        self._result = result
        self.calls: list[tuple[str, str]] = []

    async def ground(
        self, technology_name: str, use_case: str
    ) -> GroundedJustification | None:
        self.calls.append((technology_name, use_case))
        return self._result


class FakeUoW(RecommendationsUnitOfWork):
    def __init__(self, repository: FakeRecommendationRepository) -> None:
        self.recommendation_repository = repository
        self.commits = 0

    async def __aenter__(self) -> "FakeUoW":
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


@pytest.mark.anyio
async def test_generate_recommendations_persists_matches() -> None:
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

    use_case = GenerateRecommendations(lambda: uow, profile_source, catalog_source)
    views = await use_case.execute(GenerateRecommendationsInput(startup_id=startup_id))

    assert len(views) == 1
    assert views[0].technology_slug == "nvidia-nim"
    assert views[0].startup_id == startup_id
    assert uow.commits == 1
    assert len(repository.items) == 1


@pytest.mark.anyio
async def test_generate_recommendations_replaces_previous_batch() -> None:
    startup_id = uuid4()
    repository = FakeRecommendationRepository()
    await repository.save(
        Recommendation(
            startup_id=startup_id,
            technology_slug="old-tech",
            technology_name="Old Tech",
            category="legacy",
            score=0.5,
            justification="recomendacao antiga",
        )
    )
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(
        StartupProfileSnapshot(sector="LLM and generative AI", description=None, evidences=())
    )
    catalog_source = FakeCatalogSource([NIM_SNAPSHOT])

    use_case = GenerateRecommendations(lambda: uow, profile_source, catalog_source)
    await use_case.execute(GenerateRecommendationsInput(startup_id=startup_id))

    remaining_slugs = [rec.technology_slug for rec in repository.items.values()]
    assert "old-tech" not in remaining_slugs
    assert startup_id in repository.deleted_for_startup


@pytest.mark.anyio
async def test_generate_recommendations_propagates_unavailable_profile() -> None:
    repository = FakeRecommendationRepository()
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(None)
    catalog_source = FakeCatalogSource([NIM_SNAPSHOT])

    use_case = GenerateRecommendations(lambda: uow, profile_source, catalog_source)

    with pytest.raises(StartupProfileUnavailableError):
        await use_case.execute(GenerateRecommendationsInput(startup_id=uuid4()))


@pytest.mark.anyio
async def test_generate_recommendations_tracks_evidence_ids() -> None:
    startup_id = uuid4()
    evidence_id = uuid4()
    repository = FakeRecommendationRepository()
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(
        StartupProfileSnapshot(
            sector=None,
            description=None,
            evidences=(
                EvidenceSnapshot(
                    evidence_id=evidence_id,
                    title="Our new generative AI inference API deployment",
                    notes="microservice rollout",
                ),
            ),
        )
    )
    catalog_source = FakeCatalogSource([NIM_SNAPSHOT])

    use_case = GenerateRecommendations(lambda: uow, profile_source, catalog_source)
    views = await use_case.execute(GenerateRecommendationsInput(startup_id=startup_id))

    assert len(views) == 1
    assert views[0].evidence_ids == [evidence_id]


@pytest.mark.anyio
async def test_generate_recommendations_uses_profile_only_justification_for_workload_admission() -> None:
    startup_id = uuid4()
    repository = FakeRecommendationRepository()
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(
        StartupProfileSnapshot(
            sector="Pricing optimization",
            description="Processes millions of prices per day.",
            evidences=(),
            ai_profile=AIProfileSnapshot(
                ai_workload_type="analytics",
                deployment_stage="production",
                gpu_need="unknown",
                has_operational_signal=True,
            ),
        )
    )
    catalog_source = FakeCatalogSource([RAPIDS_SNAPSHOT])

    use_case = GenerateRecommendations(lambda: uow, profile_source, catalog_source)
    views = await use_case.execute(GenerateRecommendationsInput(startup_id=startup_id))

    assert len(views) == 1
    assert views[0].technology_slug == "rapids"
    assert views[0].matched_keywords == []
    assert "perfil estruturado indica alinhamento" in views[0].justification
    assert "ponto de entrada natural" not in views[0].justification


@pytest.mark.anyio
async def test_generate_recommendations_uses_grounded_justification_when_available() -> None:
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
    grounded = GroundedJustification(
        text="NVIDIA NIM acelera a inferencia de LLMs em producao.",
        citation_urls=("https://nvidia.com/nim",),
    )
    grounder = FakeGrounder(grounded)

    use_case = GenerateRecommendations(
        lambda: uow, profile_source, catalog_source, grounder=grounder
    )
    views = await use_case.execute(GenerateRecommendationsInput(startup_id=startup_id))

    assert len(views) == 1
    assert "NVIDIA NIM acelera a inferencia" in views[0].justification
    assert "[Fonte 1](https://nvidia.com/nim)" in views[0].justification
    assert "https://nvidia.com/nim" in views[0].justification
    assert grounder.calls == [("NVIDIA NIM", "servir LLMs em producao")]


class FakeSemanticSelector(NvidiaSemanticCandidateSelector):
    def __init__(self, slugs: set[str] | None = None) -> None:
        self._slugs: set[str] = slugs if slugs is not None else set()
        self.calls: list[tuple[str, dict]] = []

    async def select(
        self, query: str, technology_keywords: dict[str, tuple[str, ...]]
    ) -> set[str]:
        self.calls.append((query, technology_keywords))
        return self._slugs


RIVA_SNAPSHOT = NvidiaTechnologySnapshot(
    slug="nvidia-riva",
    name="NVIDIA Riva",
    category="speech",
    use_cases=("reconhecimento de fala",),
    keywords=("speech", "asr", "tts", "voice"),
)


@pytest.mark.anyio
async def test_semantic_selector_filters_out_technology_not_in_semantic_results() -> None:
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
    catalog_source = FakeCatalogSource([NIM_SNAPSHOT, RIVA_SNAPSHOT])
    # Semantic selector encontrou so NIM no conteudo NVIDIA
    semantic_selector = FakeSemanticSelector(slugs={"nvidia-nim"})

    use_case = GenerateRecommendations(
        lambda: uow,
        profile_source,
        catalog_source,
        semantic_selector=semantic_selector,
    )
    views = await use_case.execute(GenerateRecommendationsInput(startup_id=startup_id))

    slugs = [v.technology_slug for v in views]
    assert "nvidia-nim" in slugs
    assert "nvidia-riva" not in slugs


@pytest.mark.anyio
async def test_semantic_selector_empty_result_falls_back_to_all_candidates() -> None:
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
    # Selector retorna vazio = nvidia_knowledge nao indexado -> fallback
    semantic_selector = FakeSemanticSelector(slugs=set())

    use_case = GenerateRecommendations(
        lambda: uow,
        profile_source,
        catalog_source,
        semantic_selector=semantic_selector,
    )
    views = await use_case.execute(GenerateRecommendationsInput(startup_id=startup_id))

    # NIM ainda aparece (fallback para todos os candidatos)
    assert any(v.technology_slug == "nvidia-nim" for v in views)


@pytest.mark.anyio
async def test_without_semantic_selector_all_candidates_are_considered() -> None:
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

    # Sem selector — comportamento anterior preservado
    use_case = GenerateRecommendations(lambda: uow, profile_source, catalog_source)
    views = await use_case.execute(GenerateRecommendationsInput(startup_id=startup_id))

    assert any(v.technology_slug == "nvidia-nim" for v in views)


@pytest.mark.anyio
async def test_generate_recommendations_falls_back_to_template_when_grounder_returns_none() -> None:
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
    grounder = FakeGrounder(None)

    use_case = GenerateRecommendations(
        lambda: uow, profile_source, catalog_source, grounder=grounder
    )
    views = await use_case.execute(GenerateRecommendationsInput(startup_id=startup_id))

    assert len(views) == 1
    assert "Evidencias e perfil mencionam:" in views[0].justification
    assert grounder.calls == [("NVIDIA NIM", "servir LLMs em producao")]


INCEPTION_SNAPSHOT = NvidiaTechnologySnapshot(
    slug="nvidia-inception",
    name="NVIDIA Inception",
    category="startup_program",
    use_cases=("programa de aceleração para startups de IA",),
    keywords=("startup", "accelerator", "inception"),
)


@pytest.mark.anyio
async def test_inception_floor_injected_when_no_matches() -> None:
    """P4: quando nenhuma tecnologia e' recomendada, Inception e' injetado como floor."""

    startup_id = uuid4()
    repository = FakeRecommendationRepository()
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(
        StartupProfileSnapshot(
            sector="hr tech",
            description="Payroll and onboarding platform for small businesses.",
            evidences=(),
        )
    )
    # Apenas Inception no catalogo — zero keywords batem com o perfil
    catalog_source = FakeCatalogSource([INCEPTION_SNAPSHOT])

    use_case = GenerateRecommendations(lambda: uow, profile_source, catalog_source)
    views = await use_case.execute(GenerateRecommendationsInput(startup_id=startup_id))

    assert len(views) == 1
    assert views[0].technology_slug == "nvidia-inception"
    assert views[0].score == 0.21
    assert views[0].confidence == 0.10
    assert "ponto de entrada" in views[0].justification


@pytest.mark.anyio
async def test_inception_floor_not_injected_when_matches_exist() -> None:
    """P4: quando ha recomendacoes normais, o floor do Inception nao e injetado."""

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
    catalog_source = FakeCatalogSource([NIM_SNAPSHOT, INCEPTION_SNAPSHOT])

    use_case = GenerateRecommendations(lambda: uow, profile_source, catalog_source)
    views = await use_case.execute(GenerateRecommendationsInput(startup_id=startup_id))

    slugs = [v.technology_slug for v in views]
    assert "nvidia-nim" in slugs
    assert "nvidia-inception" not in slugs
