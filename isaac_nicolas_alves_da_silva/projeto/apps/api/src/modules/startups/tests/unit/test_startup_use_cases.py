"""Testes dos casos de uso do modulo startups."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.startups.application.dto import (
    AddStartupEvidenceInput,
    CreateStartupInput,
    ListStartupsInput,
    UpdateStartupInput,
)
from apps.api.src.modules.startups.application.unit_of_work import StartupsUnitOfWork
from apps.api.src.modules.startups.application.use_cases.add_startup_evidence import (
    AddStartupEvidence,
)
from apps.api.src.modules.startups.application.use_cases.create_startup import (
    CreateStartup,
)
from apps.api.src.modules.startups.application.use_cases.get_startup import GetStartup
from apps.api.src.modules.startups.application.use_cases.list_startup_evidences import (
    ListStartupEvidences,
)
from apps.api.src.modules.startups.application.use_cases.list_startups import (
    ListStartups,
)
from apps.api.src.modules.startups.application.use_cases.update_startup import (
    UpdateStartup,
)
from apps.api.src.modules.startups.domain.entities import Startup, StartupEvidence
from apps.api.src.modules.startups.domain.enums import (
    AiMaturityLevel,
    FundingStage,
    StartupEvidenceType,
)
from apps.api.src.modules.startups.domain.exceptions import StartupNotFoundError
from apps.api.src.modules.startups.domain.repositories import (
    StartupEvidenceRepository,
    StartupRepository,
)


class FakeStartupRepository(StartupRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, Startup] = {}

    async def save(self, startup: Startup) -> None:
        self.items[startup.id] = startup

    async def get_by_id(self, startup_id: UUID) -> Startup | None:
        return self.items.get(startup_id)

    async def list_page(
        self,
        *,
        page: int,
        page_size: int,
        query: str | None = None,
        sector: str | None = None,
        country: str | None = None,
        ai_maturity_level=None,
    ) -> tuple[list[Startup], int]:
        startups = list(self.items.values())
        if query:
            term = query.lower()
            startups = [
                startup
                for startup in startups
                if term in startup.name.lower()
                or term in (startup.description or "").lower()
            ]
        if sector:
            startups = [s for s in startups if s.sector and s.sector.lower() == sector.lower()]
        if country:
            startups = [s for s in startups if s.country and s.country.lower() == country.lower()]
        if ai_maturity_level:
            startups = [s for s in startups if s.ai_maturity_level is ai_maturity_level]
        startups.sort(key=lambda startup: (startup.updated_at, startup.id), reverse=True)
        total = len(startups)
        start = (page - 1) * page_size
        return startups[start : start + page_size], total

    async def list_all(self) -> list[Startup]:
        return list(self.items.values())

    async def count_by_maturity(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for startup in self.items.values():
            key = startup.ai_maturity_level.value if startup.ai_maturity_level else "unclassified"
            result[key] = result.get(key, 0) + 1
        return result


class FakeEvidenceRepository(StartupEvidenceRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, StartupEvidence] = {}

    async def save(self, evidence: StartupEvidence) -> None:
        self.items[evidence.id] = evidence

    async def get_by_id(self, evidence_id: UUID) -> StartupEvidence | None:
        return self.items.get(evidence_id)

    async def list_by_startup_id(self, startup_id: UUID) -> list[StartupEvidence]:
        return [
            evidence
            for evidence in self.items.values()
            if evidence.startup_id == startup_id
        ]


class FakeUoW(StartupsUnitOfWork):
    def __init__(
        self,
        startup_repository: FakeStartupRepository,
        evidence_repository: FakeEvidenceRepository,
    ) -> None:
        self.startup_repository = startup_repository
        self.evidence_repository = evidence_repository
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


def _make_uow() -> FakeUoW:
    return FakeUoW(FakeStartupRepository(), FakeEvidenceRepository())


@pytest.mark.anyio
async def test_create_startup_persists_and_returns_view() -> None:
    uow = _make_uow()
    use_case = CreateStartup(lambda: uow)

    view = await use_case.execute(
        CreateStartupInput(
            name="Acme AI",
            website_url="https://acme.example.com",
            sector="AI Infra",
        )
    )

    assert view.name == "Acme AI"
    assert view.id in uow.startup_repository.items
    assert uow.commits == 1


@pytest.mark.anyio
async def test_create_startup_infers_brazil_from_br_domain() -> None:
    uow = _make_uow()
    use_case = CreateStartup(lambda: uow)

    view = await use_case.execute(
        CreateStartupInput(
            name="Acme Brasil AI",
            website_url="https://acme.com.br",
        )
    )

    assert view.country == "BR"


@pytest.mark.anyio
async def test_create_startup_via_public_contract_returns_id() -> None:
    uow = _make_uow()
    use_case = CreateStartup(lambda: uow)

    startup_id = await use_case.create_startup(
        name="Acme AI", website_url="https://acme.example.com"
    )

    assert uow.startup_repository.items[startup_id].name == "Acme AI"


@pytest.mark.anyio
async def test_create_startup_reuses_existing_record_on_domain_match() -> None:
    uow = _make_uow()
    existing = Startup(name="Acme Inc", website_url="https://www.acme.com/about")
    await uow.startup_repository.save(existing)
    use_case = CreateStartup(lambda: uow)

    view = await use_case.execute(
        CreateStartupInput(name="Acme Artificial Intelligence", website_url="https://acme.com/")
    )

    assert view.id == existing.id
    assert len(uow.startup_repository.items) == 1
    assert uow.commits == 0


@pytest.mark.anyio
async def test_create_startup_reuses_existing_record_on_name_match() -> None:
    uow = _make_uow()
    existing = Startup(name="Dadosfera")
    await uow.startup_repository.save(existing)
    use_case = CreateStartup(lambda: uow)

    view = await use_case.execute(
        CreateStartupInput(name="Dadosfera Tecnologia", website_url=None)
    )

    assert view.id == existing.id
    assert len(uow.startup_repository.items) == 1


@pytest.mark.anyio
async def test_create_startup_creates_new_record_when_not_a_duplicate() -> None:
    uow = _make_uow()
    existing = Startup(name="Totally Unrelated Co")
    await uow.startup_repository.save(existing)
    use_case = CreateStartup(lambda: uow)

    view = await use_case.execute(CreateStartupInput(name="Acme AI"))

    assert view.id != existing.id
    assert len(uow.startup_repository.items) == 2
    assert uow.commits == 1


@pytest.mark.anyio
async def test_get_startup_returns_existing_startup() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)

    view = await GetStartup(lambda: uow).execute(startup_id=startup.id)

    assert view.id == startup.id


@pytest.mark.anyio
async def test_get_startup_raises_when_missing() -> None:
    uow = _make_uow()

    with pytest.raises(StartupNotFoundError):
        await GetStartup(lambda: uow).execute(startup_id=uuid4())


@pytest.mark.anyio
async def test_list_startups_filters_and_paginates_portfolio() -> None:
    uow = _make_uow()
    alpha = Startup(name="Alpha AI", sector="Healthcare", country="BR")
    alpha.classify(AiMaturityLevel.AI_NATIVE, "Modelo proprio")
    beta = Startup(name="Beta Cloud", sector="Infrastructure", country="US")
    gamma = Startup(name="Gamma AI", sector="Healthcare", country="BR")
    for startup in (alpha, beta, gamma):
        await uow.startup_repository.save(startup)

    page = await ListStartups(lambda: uow).execute(
        ListStartupsInput(
            page=1,
            page_size=1,
            query="ai",
            sector="healthcare",
            country="br",
            ai_maturity_level=AiMaturityLevel.AI_NATIVE,
        )
    )

    assert page.total == 1
    assert page.items[0].id == alpha.id


@pytest.mark.anyio
async def test_update_startup_changes_existing_record() -> None:
    uow = _make_uow()
    startup = Startup(name="Old")
    await uow.startup_repository.save(startup)

    view = await UpdateStartup(lambda: uow).execute(
        UpdateStartupInput(startup_id=startup.id, name="New", country="BR")
    )

    assert view.name == "New"
    assert view.country == "BR"
    assert uow.startup_repository.items[startup.id].name == "New"


@pytest.mark.anyio
async def test_update_startup_sets_structured_fields() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)

    view = await UpdateStartup(lambda: uow).execute(
        UpdateStartupInput(
            startup_id=startup.id,
            founders=["Ana Silva"],
            funding_stage=FundingStage.SERIES_A,
            funding_amount_usd=2_000_000.0,
            customers=["Empresa X"],
        )
    )

    assert view.founders == ["Ana Silva"]
    assert view.funding_stage is FundingStage.SERIES_A
    assert view.funding_amount_usd == 2_000_000.0
    assert view.customers == ["Empresa X"]


@pytest.mark.anyio
async def test_add_evidence_requires_existing_startup() -> None:
    uow = _make_uow()

    with pytest.raises(StartupNotFoundError):
        await AddStartupEvidence(lambda: uow).execute(
            AddStartupEvidenceInput(
                startup_id=uuid4(),
                scraping_result_id=uuid4(),
                source_url="https://example.com",
            )
        )


@pytest.mark.anyio
async def test_attach_evidence_via_public_contract() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)
    scraping_result_id = uuid4()

    await AddStartupEvidence(lambda: uow).attach_evidence(
        startup_id=startup.id,
        scraping_result_id=scraping_result_id,
        source_url="https://acme.example.com",
        title="Acme",
        notes="conteudo",
    )

    evidences = await ListStartupEvidences(lambda: uow).execute(
        startup_id=startup.id
    )
    assert len(evidences) == 1
    assert evidences[0].scraping_result_id == scraping_result_id


@pytest.mark.anyio
async def test_add_and_list_startup_evidences() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)

    evidence_view = await AddStartupEvidence(lambda: uow).execute(
        AddStartupEvidenceInput(
            startup_id=startup.id,
            scraping_result_id=uuid4(),
            source_url="https://example.com/news",
            evidence_type=StartupEvidenceType.NEWS,
            confidence_score=0.9,
        )
    )
    evidences = await ListStartupEvidences(lambda: uow).execute(
        startup_id=startup.id
    )

    assert evidence_view.evidence_type is StartupEvidenceType.NEWS
    assert len(evidences) == 1
    assert evidences[0].id == evidence_view.id


@pytest.mark.anyio
async def test_add_startup_evidence_infers_technical_type_from_jobs_and_github() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)

    evidence_view = await AddStartupEvidence(lambda: uow).execute(
        AddStartupEvidenceInput(
            startup_id=startup.id,
            scraping_result_id=uuid4(),
            source_url="https://github.com/acme-ai/platform",
            title="Acme AI platform",
            notes="requirements.txt includes PyTorch and CUDA.",
        )
    )

    assert evidence_view.evidence_type is StartupEvidenceType.TECHNICAL


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "https://www.terra.com.br/noticias/dino/neuralmind",
        "https://revistapesquisa.fapesp.br/cresce-o-apoio-a-startups",
        "https://bhtec.org.br/2025/10/10/neuralmind",
        "https://parque.inova.unicamp.br/neuralmind-programa-google",
    ],
)
async def test_add_startup_evidence_infers_news_type_from_news_hosts(
    url: str,
) -> None:
    uow = _make_uow()
    startup = Startup(name="NeuralMind")
    await uow.startup_repository.save(startup)

    evidence_view = await AddStartupEvidence(lambda: uow).execute(
        AddStartupEvidenceInput(
            startup_id=startup.id,
            scraping_result_id=uuid4(),
            source_url=url,
            title="NeuralMind recebe apoio para IA",
            notes="Empresa treina modelos BERT em portugues.",
        )
    )

    assert evidence_view.evidence_type is StartupEvidenceType.NEWS


@pytest.mark.anyio
async def test_add_startup_evidence_infers_website_type_for_plain_site() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)

    evidence_view = await AddStartupEvidence(lambda: uow).execute(
        AddStartupEvidenceInput(
            startup_id=startup.id,
            scraping_result_id=uuid4(),
            source_url="https://acme.example.com/about",
            title="About Acme",
        )
    )

    assert evidence_view.evidence_type is StartupEvidenceType.WEBSITE
