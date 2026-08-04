"""Testes unitarios do modulo startup_discovery."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.startup_discovery.application.dto import StartupCandidate
from apps.api.src.modules.startup_discovery.application.ports import HubLinkExtractor
from apps.api.src.modules.startup_discovery.application.use_cases.get_discovery_run import (
    GetDiscoveryRun,
)
from apps.api.src.modules.startup_discovery.application.use_cases.run_discovery import (
    RunStartupDiscovery,
)
from apps.api.src.modules.startup_discovery.domain.entities import (
    DiscoveryRun,
    DiscoverySubmission,
)
from apps.api.src.modules.startup_discovery.domain.enums import DiscoveryRunStatus
from apps.api.src.modules.startup_discovery.domain.exceptions import (
    DiscoveryRunNotFoundError,
)
from apps.api.src.modules.startup_discovery.domain.hub_registry import HUB_SOURCES


class FakeDiscoveryRunRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, DiscoveryRun] = {}
        self.submissions: dict[UUID, list[DiscoverySubmission]] = {}

    async def save(self, run: DiscoveryRun) -> None:
        self.items[run.id] = run

    async def get_by_id(self, run_id: UUID) -> DiscoveryRun | None:
        return self.items.get(run_id)

    async def list_recent(self, *, limit: int = 20) -> list[DiscoveryRun]:
        all_runs = sorted(self.items.values(), key=lambda r: r.created_at, reverse=True)
        return all_runs[:limit]

    async def save_submission(self, submission: DiscoverySubmission) -> None:
        submissions = self.submissions.setdefault(submission.run_id, [])
        for index, existing in enumerate(submissions):
            if existing.id == submission.id:
                submissions[index] = submission
                return
        submissions.append(submission)

    async def list_submissions_for_run(
        self,
        run_id: UUID,
    ) -> list[DiscoverySubmission]:
        return self.submissions.get(run_id, [])


class FakeUnitOfWork:
    def __init__(self, repository: FakeDiscoveryRunRepository) -> None:
        self.repository = repository
        self._committed = False

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        pass

    async def commit(self) -> None:
        self._committed = True


class FakeHubExtractor(HubLinkExtractor):
    def __init__(self, urls: list[str]) -> None:
        self._urls = urls

    async def extract(self, listing_url: str, *, limit: int) -> list[str]:
        return self._urls[:limit]


class FakeCandidateExtractor(HubLinkExtractor):
    def __init__(self, candidates: list[StartupCandidate]) -> None:
        self._candidates = candidates

    async def extract(
        self,
        listing_url: str,
        *,
        limit: int,
    ) -> list[StartupCandidate]:
        return self._candidates[:limit]


class FailingHubExtractor(HubLinkExtractor):
    async def extract(self, listing_url: str, *, limit: int) -> list[str]:
        raise RuntimeError("hub offline")


class FakeUrlSubmitter:
    def __init__(self) -> None:
        self.submitted: list[str] = []
        self.submitted_names: list[str | None] = []

    async def submit(self, url: str, *, name: str | None = None) -> UUID:
        self.submitted.append(url)
        self.submitted_names.append(name)
        return uuid4()


def make_uow_factory(repo: FakeDiscoveryRunRepository):
    def factory():
        return FakeUnitOfWork(repo)

    return factory


@pytest.mark.anyio
async def test_run_discovery_completes_with_submitted_urls():
    repo = FakeDiscoveryRunRepository()
    submitter = FakeUrlSubmitter()
    extractors = {
        hub.extractor_type: FakeHubExtractor(
            [f"https://startup{i}.com" for i in range(5)]
        )
        for hub in HUB_SOURCES
    }

    use_case = RunStartupDiscovery(
        uow_factory=make_uow_factory(repo),
        extractors=extractors,
        url_ingestion_submitter=submitter,
        max_per_run=10,
    )

    view = await use_case.execute()

    assert view.status == DiscoveryRunStatus.COMPLETED
    assert view.jobs_submitted > 0
    assert len(submitter.submitted) > 0


@pytest.mark.anyio
async def test_run_discovery_respects_max_per_run_limit():
    repo = FakeDiscoveryRunRepository()
    submitter = FakeUrlSubmitter()
    extractors = {
        hub.extractor_type: FakeHubExtractor([f"https://s{i}.com" for i in range(15)])
        for hub in HUB_SOURCES
    }

    use_case = RunStartupDiscovery(
        uow_factory=make_uow_factory(repo),
        extractors=extractors,
        url_ingestion_submitter=submitter,
        max_per_run=7,
    )

    view = await use_case.execute()

    assert len(submitter.submitted) <= 7
    assert view.jobs_submitted <= 7


@pytest.mark.anyio
async def test_run_discovery_propagates_candidate_metadata():
    repo = FakeDiscoveryRunRepository()
    submitter = FakeUrlSubmitter()
    candidate = StartupCandidate(
        website_url="https://startup.ai",
        name="Startup AI",
        hub_profile_url="https://hub.example/startup-ai",
        short_description="Plataforma brasileira de IA para operacoes.",
        declared_sector="AI",
    )
    extractors = {hub.extractor_type: FailingHubExtractor() for hub in HUB_SOURCES}
    extractors[HUB_SOURCES[0].extractor_type] = FakeCandidateExtractor([candidate])

    use_case = RunStartupDiscovery(
        uow_factory=make_uow_factory(repo),
        extractors=extractors,
        url_ingestion_submitter=submitter,
        max_per_run=10,
    )

    view = await use_case.execute()

    assert submitter.submitted == ["https://startup.ai"]
    assert submitter.submitted_names == ["Startup AI"]
    assert view.submitted_urls[0].name == "Startup AI"
    assert view.submitted_urls[0].hub_profile_url == "https://hub.example/startup-ai"
    assert view.submitted_urls[0].short_description.startswith("Plataforma brasileira")


@pytest.mark.anyio
async def test_run_discovery_skips_consultancy_url_candidate():
    repo = FakeDiscoveryRunRepository()
    submitter = FakeUrlSubmitter()
    consultancy = StartupCandidate(
        website_url="https://consultoria-dados.example.com",
        name="Consultoria Dados",
        short_description="Consultoria de dados e outsourcing para empresas.",
        declared_sector="Data services",
    )
    product = StartupCandidate(
        website_url="https://startup-ai.example.com",
        name="Startup AI",
        short_description="Plataforma SaaS de IA para operacoes.",
        declared_sector="AI",
    )
    extractors = {hub.extractor_type: FailingHubExtractor() for hub in HUB_SOURCES}
    extractors[HUB_SOURCES[0].extractor_type] = FakeCandidateExtractor(
        [consultancy, product]
    )

    use_case = RunStartupDiscovery(
        uow_factory=make_uow_factory(repo),
        extractors=extractors,
        url_ingestion_submitter=submitter,
        max_per_run=10,
    )

    view = await use_case.execute()

    assert view.status == DiscoveryRunStatus.COMPLETED
    assert submitter.submitted == ["https://startup-ai.example.com"]
    assert view.jobs_submitted == 1


@pytest.mark.anyio
async def test_run_discovery_skips_failing_hub_best_effort():
    repo = FakeDiscoveryRunRepository()
    submitter = FakeUrlSubmitter()

    hub_names = [hub.extractor_type for hub in HUB_SOURCES]
    extractors = {name: FailingHubExtractor() for name in hub_names}
    if hub_names:
        extractors[hub_names[0]] = FakeHubExtractor(["https://startupok.com"])

    use_case = RunStartupDiscovery(
        uow_factory=make_uow_factory(repo),
        extractors=extractors,
        url_ingestion_submitter=submitter,
        max_per_run=10,
    )

    view = await use_case.execute()

    assert view.status == DiscoveryRunStatus.COMPLETED
    assert len(submitter.submitted) >= 1


@pytest.mark.anyio
async def test_run_discovery_fails_when_all_hubs_fail():
    repo = FakeDiscoveryRunRepository()
    submitter = FakeUrlSubmitter()
    extractors = {hub.extractor_type: FailingHubExtractor() for hub in HUB_SOURCES}

    use_case = RunStartupDiscovery(
        uow_factory=make_uow_factory(repo),
        extractors=extractors,
        url_ingestion_submitter=submitter,
        max_per_run=10,
    )

    view = await use_case.execute()

    assert view.status == DiscoveryRunStatus.FAILED
    assert view.error_message is not None
    assert "hub offline" in view.error_message


@pytest.mark.anyio
async def test_get_discovery_run_returns_view_by_id():
    repo = FakeDiscoveryRunRepository()
    run = DiscoveryRun()
    run.start()
    run.complete(hubs_processed=1, urls_found=3, jobs_submitted=3)
    await repo.save(run)
    await repo.save_submission(
        DiscoverySubmission(
            run_id=run.id,
            hub_name="InovAtiva Brasil",
            website_url="https://startupok.com",
            job_id=uuid4(),
            name="Startup OK",
        )
    )

    use_case = GetDiscoveryRun(make_uow_factory(repo))
    view = await use_case.execute(run.id)

    assert view.id == run.id
    assert view.status == DiscoveryRunStatus.COMPLETED
    assert view.submitted_urls[0].name == "Startup OK"


@pytest.mark.anyio
async def test_get_discovery_run_raises_not_found():
    repo = FakeDiscoveryRunRepository()
    use_case = GetDiscoveryRun(make_uow_factory(repo))

    with pytest.raises(DiscoveryRunNotFoundError):
        await use_case.execute(uuid4())


def test_discovery_run_entity_status_transitions():
    run = DiscoveryRun()
    assert run.status == DiscoveryRunStatus.PENDING

    run.start()
    assert run.status == DiscoveryRunStatus.RUNNING

    run.complete(hubs_processed=2, urls_found=10, jobs_submitted=10)
    assert run.status == DiscoveryRunStatus.COMPLETED
    assert run.hubs_processed == 2
    assert run.urls_found == 10


def test_discovery_run_entity_fail_transition():
    run = DiscoveryRun()
    run.start()
    run.fail("tudo quebrou")
    assert run.status == DiscoveryRunStatus.FAILED
    assert run.error_message == "tudo quebrou"
