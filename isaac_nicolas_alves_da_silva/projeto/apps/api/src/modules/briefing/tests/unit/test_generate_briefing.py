"""Testes do caso de uso GenerateBriefing."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.briefing.application.dto import (
    EvidenceSnapshot,
    GenerateBriefingInput,
    GroundedContext,
    RecommendationSnapshot,
    StartupAIProfileSnapshot,
    StartupProfileSnapshot,
    StartupSnapshot,
)
from apps.api.src.modules.briefing.application.ports import (
    NvidiaContextGrounder,
    RecommendationsSource,
    StartupProfileSource,
)
from apps.api.src.modules.briefing.application.unit_of_work import (
    BriefingsUnitOfWork,
)
from apps.api.src.modules.briefing.application.use_cases.generate_briefing import (
    GenerateBriefing,
)
from apps.api.src.modules.briefing.domain.entities import Briefing
from apps.api.src.modules.briefing.domain.exceptions import (
    StartupProfileUnavailableError,
)
from apps.api.src.modules.briefing.domain.repositories import BriefingRepository

STARTUP_SNAPSHOT = StartupSnapshot(
    name="Acme AI",
    sector="LLM customer service",
    description="Plataforma de atendimento com LLM.",
    country="BR",
    website_url="https://acme.example.com",
)


class FakeProfileSource(StartupProfileSource):
    def __init__(self, profile: StartupProfileSnapshot | None) -> None:
        self._profile = profile

    async def get_profile(self, startup_id: UUID) -> StartupProfileSnapshot:
        if self._profile is None:
            raise StartupProfileUnavailableError(f"Startup {startup_id} nao encontrada.")
        return self._profile


class FakeRecommendationsSource(RecommendationsSource):
    def __init__(self, recommendations: list[RecommendationSnapshot]) -> None:
        self._recommendations = recommendations

    async def list_by_startup(self, startup_id: UUID) -> list[RecommendationSnapshot]:
        return self._recommendations


class FakeBriefingRepository(BriefingRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, Briefing] = {}
        self.deleted_for_startup: list[UUID] = []

    async def save(self, briefing: Briefing) -> None:
        self.items[briefing.id] = briefing

    async def delete_by_startup_id(self, startup_id: UUID) -> None:
        self.deleted_for_startup.append(startup_id)
        self.items = {
            briefing_id: briefing
            for briefing_id, briefing in self.items.items()
            if briefing.startup_id != startup_id
        }

    async def get_by_id(self, briefing_id: UUID) -> Briefing | None:
        return self.items.get(briefing_id)

    async def list_by_startup_id(self, startup_id: UUID) -> list[Briefing]:
        return [b for b in self.items.values() if b.startup_id == startup_id]

    async def update_content(self, briefing_id: UUID, content: str) -> None:
        briefing = self.items.get(briefing_id)
        if briefing is not None:
            briefing.content = content

    async def update_review(self, briefing: Briefing) -> None:
        if briefing.id in self.items:
            self.items[briefing.id] = briefing


class FakeGrounder(NvidiaContextGrounder):
    def __init__(self, result: GroundedContext | None) -> None:
        self._result = result
        self.calls: list[tuple[str | None, tuple[str, ...]]] = []

    async def ground(
        self, sector: str | None, technology_names: tuple[str, ...]
    ) -> GroundedContext | None:
        self.calls.append((sector, technology_names))
        return self._result


class FakeUoW(BriefingsUnitOfWork):
    def __init__(self, repository: FakeBriefingRepository) -> None:
        self.briefing_repository = repository
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
async def test_generate_briefing_persists_markdown_content() -> None:
    startup_id = uuid4()
    repository = FakeBriefingRepository()
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(
        StartupProfileSnapshot(
            startup=STARTUP_SNAPSHOT,
            evidences=(
                EvidenceSnapshot(
                    title="Acme launches LLM chatbot",
                    source_url="https://example.com/news",
                    evidence_type="news",
                    confidence_score=0.9,
                ),
            ),
        )
    )
    recommendations_source = FakeRecommendationsSource(
        [
            RecommendationSnapshot(
                technology_name="NVIDIA NIM",
                category="model_serving",
                score=0.8,
                confidence=0.75,
                complexity="medium",
                justification="Evidencias mencionam llm e inference.",
                nivel="forte",
                signal_origins=("llm: evidencia acme",),
            )
        ]
    )

    use_case = GenerateBriefing(lambda: uow, profile_source, recommendations_source)
    view = await use_case.execute(GenerateBriefingInput(startup_id=startup_id))

    assert view.startup_id == startup_id
    assert "Acme AI" in view.content
    assert "NVIDIA NIM" in view.content
    assert "## Tese de Fit NVIDIA" in view.content
    assert "## Matriz de Recomendacoes" in view.content
    assert "fit 80%" in view.content
    assert "confianca 75%" in view.content
    assert uow.commits == 1
    assert len(repository.items) == 1


@pytest.mark.anyio
async def test_generate_briefing_replaces_previous_briefing() -> None:
    startup_id = uuid4()
    repository = FakeBriefingRepository()
    await repository.save(Briefing(startup_id=startup_id, content="briefing antigo"))
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(
        StartupProfileSnapshot(startup=STARTUP_SNAPSHOT, evidences=())
    )
    recommendations_source = FakeRecommendationsSource([])

    use_case = GenerateBriefing(lambda: uow, profile_source, recommendations_source)
    await use_case.execute(GenerateBriefingInput(startup_id=startup_id))

    assert startup_id in repository.deleted_for_startup
    remaining_contents = [b.content for b in repository.items.values()]
    assert "briefing antigo" not in remaining_contents


@pytest.mark.anyio
async def test_generate_briefing_propagates_unavailable_profile() -> None:
    repository = FakeBriefingRepository()
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(None)
    recommendations_source = FakeRecommendationsSource([])

    use_case = GenerateBriefing(lambda: uow, profile_source, recommendations_source)

    with pytest.raises(StartupProfileUnavailableError):
        await use_case.execute(GenerateBriefingInput(startup_id=uuid4()))


@pytest.mark.anyio
async def test_generate_briefing_includes_nvidia_context_when_grounder_succeeds() -> None:
    startup_id = uuid4()
    repository = FakeBriefingRepository()
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(
        StartupProfileSnapshot(startup=STARTUP_SNAPSHOT, evidences=())
    )
    recommendations_source = FakeRecommendationsSource(
        [
            RecommendationSnapshot(
                technology_name="NVIDIA NIM",
                category="model_serving",
                score=0.8,
                justification="Evidencias mencionam llm e inference.",
            )
        ]
    )
    grounded = GroundedContext(
        text="NVIDIA NIM e NeMo aceleram atendimento via LLM no setor.",
        citation_urls=("https://nvidia.com/nim",),
    )
    grounder = FakeGrounder(grounded)

    use_case = GenerateBriefing(
        lambda: uow, profile_source, recommendations_source, grounder=grounder
    )
    view = await use_case.execute(GenerateBriefingInput(startup_id=startup_id))

    assert "## Contexto NVIDIA" in view.content
    assert "NVIDIA NIM e NeMo aceleram atendimento" in view.content
    assert "[Fonte 1](https://nvidia.com/nim)" in view.content
    assert grounder.calls == [(STARTUP_SNAPSHOT.sector, ("NVIDIA NIM",))]


@pytest.mark.anyio
async def test_generate_briefing_includes_ai_profile() -> None:
    startup_id = uuid4()
    repository = FakeBriefingRepository()
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(
        StartupProfileSnapshot(
            startup=STARTUP_SNAPSHOT,
            evidences=(),
            ai_profile=StartupAIProfileSnapshot(
                ai_workload_type="nlp",
                deployment_stage="production",
                gpu_need="high",
                business_goal="reduzir custo de inferencia",
            ),
        )
    )
    recommendations_source = FakeRecommendationsSource([])

    use_case = GenerateBriefing(lambda: uow, profile_source, recommendations_source)
    view = await use_case.execute(GenerateBriefingInput(startup_id=startup_id))

    assert "Workload de IA: nlp" in view.content
    assert "Necessidade de GPU: high" in view.content
    assert "Objetivo de negocio: reduzir custo de inferencia" in view.content


@pytest.mark.anyio
async def test_generate_briefing_omits_nvidia_context_without_recommendations() -> None:
    startup_id = uuid4()
    repository = FakeBriefingRepository()
    uow = FakeUoW(repository)
    profile_source = FakeProfileSource(
        StartupProfileSnapshot(startup=STARTUP_SNAPSHOT, evidences=())
    )
    recommendations_source = FakeRecommendationsSource([])
    grounder = FakeGrounder(GroundedContext(text="nunca deveria chamar", citation_urls=()))

    use_case = GenerateBriefing(
        lambda: uow, profile_source, recommendations_source, grounder=grounder
    )
    view = await use_case.execute(GenerateBriefingInput(startup_id=startup_id))

    assert "## Contexto NVIDIA" not in view.content
    assert grounder.calls == []
