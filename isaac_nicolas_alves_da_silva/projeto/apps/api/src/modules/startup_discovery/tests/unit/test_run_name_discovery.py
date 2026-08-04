"""Testes unitarios do caminho name-extraction em RunStartupDiscovery."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.startup_discovery.application.dto import (
    DiscoveredCandidateItem,
    StartupCandidate,
)
from apps.api.src.modules.startup_discovery.application.ports import (
    HubLinkExtractor,
    HubNameExtractor,
)
from apps.api.src.modules.startup_discovery.application.use_cases.run_discovery import (
    RunStartupDiscovery,
)
from apps.api.src.modules.startup_discovery.domain.entities import (
    DiscoveryRun,
    DiscoverySubmission,
    StartupDiscoveryCandidate,
)
from apps.api.src.modules.startup_discovery.domain.enums import (
    CandidateStatus,
    DiscoveryRunStatus,
)
from apps.api.src.modules.startup_discovery.domain.hub_registry import HUB_SOURCES


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeDiscoveryRunRepository:
    def __init__(self) -> None:
        self.runs: dict[UUID, DiscoveryRun] = {}
        self.submissions: dict[UUID, list[DiscoverySubmission]] = {}

    async def save(self, run: DiscoveryRun) -> None:
        self.runs[run.id] = run

    async def get_by_id(self, run_id: UUID) -> DiscoveryRun | None:
        return self.runs.get(run_id)

    async def list_recent(self, *, limit: int = 20) -> list[DiscoveryRun]:
        return list(self.runs.values())[:limit]

    async def save_submission(self, submission: DiscoverySubmission) -> None:
        self.submissions.setdefault(submission.run_id, []).append(submission)

    async def list_submissions_for_run(self, run_id: UUID) -> list[DiscoverySubmission]:
        return self.submissions.get(run_id, [])


class FakeCandidateRepository:
    def __init__(self) -> None:
        self.candidates: dict[UUID, StartupDiscoveryCandidate] = {}

    async def save(self, candidate: StartupDiscoveryCandidate) -> None:
        self.candidates[candidate.id] = candidate

    async def get_by_id(self, candidate_id: UUID) -> StartupDiscoveryCandidate | None:
        return self.candidates.get(candidate_id)

    async def list_by_run_id(self, run_id: UUID) -> list[StartupDiscoveryCandidate]:
        return [c for c in self.candidates.values() if c.run_id == run_id]

    async def list_by_status(
        self, status: CandidateStatus, *, limit: int = 100
    ) -> list[StartupDiscoveryCandidate]:
        return [c for c in self.candidates.values() if c.status == status][:limit]


class FakeUnitOfWork:
    def __init__(
        self,
        run_repo: FakeDiscoveryRunRepository,
        candidate_repo: FakeCandidateRepository,
    ) -> None:
        self.repository = run_repo
        self.candidate_repository = candidate_repo

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
        pass


class FakeNameExtractor(HubNameExtractor):
    def __init__(self, items: list[DiscoveredCandidateItem]) -> None:
        self._items = items

    async def extract(
        self, listing_url: str, *, limit: int
    ) -> list[DiscoveredCandidateItem]:
        return self._items[:limit]


class FailingNameExtractor(HubNameExtractor):
    async def extract(
        self, listing_url: str, *, limit: int
    ) -> list[DiscoveredCandidateItem]:
        raise RuntimeError("js file unreachable")


class FakeUrlExtractor(HubLinkExtractor):
    async def extract(self, listing_url: str, *, limit: int) -> list[StartupCandidate]:
        return []


class FakeUrlSubmitter:
    def __init__(self) -> None:
        self.submitted: list[str] = []
        self.submitted_names: list[str | None] = []

    async def submit(self, url: str, *, name: str | None = None) -> UUID:
        self.submitted.append(url)
        self.submitted_names.append(name)
        return uuid4()


class FakeEnricher:
    """Enricher falso: enriquece candidatos com alta confianca por padrao."""

    def __init__(self, *, confidence: float = 0.90, skip_names: set[str] | None = None) -> None:
        self._confidence = confidence
        self._skip = skip_names or set()

    async def enrich_batch(
        self, candidates: list[StartupDiscoveryCandidate]
    ) -> list[StartupDiscoveryCandidate]:
        for c in candidates:
            if c.name in self._skip:
                c.reject("confidence_below_threshold: best=0.0, url=None")
            else:
                c.enrich(
                    official_website_url=f"https://{c.normalized_name}.com",
                    official_site_confidence=self._confidence,
                    enrichment_sources=[f"https://search.example/{c.normalized_name}"],
                )
        return candidates


def make_uow_factory(
    run_repo: FakeDiscoveryRunRepository,
    candidate_repo: FakeCandidateRepository,
):
    def factory():
        return FakeUnitOfWork(run_repo, candidate_repo)

    return factory


def _name_hub_extractors(items: list[DiscoveredCandidateItem]) -> dict:
    name_mode_type = next(
        (h.extractor_type for h in HUB_SOURCES if h.extraction_mode == "name"), None
    )
    return {name_mode_type: FakeNameExtractor(items)} if name_mode_type else {}


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_name_hub_saves_candidates_as_discovered_when_no_enricher():
    run_repo = FakeDiscoveryRunRepository()
    cand_repo = FakeCandidateRepository()
    items = [
        DiscoveredCandidateItem(name="Noleak", category="TOP 10 Artificial Intelligence 2025", rank=1),
        DiscoveredCandidateItem(name="NeuralMind", category="TOP 10 Artificial Intelligence 2025", rank=9),
    ]

    use_case = RunStartupDiscovery(
        uow_factory=make_uow_factory(run_repo, cand_repo),
        extractors={h.extractor_type: FakeUrlExtractor() for h in HUB_SOURCES if h.extraction_mode == "url"},
        name_extractors=_name_hub_extractors(items),
        url_ingestion_submitter=FakeUrlSubmitter(),
        candidate_enricher=None,
        max_per_run=20,
    )

    view = await use_case.execute()

    assert view.status == DiscoveryRunStatus.COMPLETED
    assert view.candidates_discovered == 2
    assert view.candidates_enriched == 0
    assert view.jobs_submitted == 0

    saved = list(cand_repo.candidates.values())
    assert len(saved) == 2
    assert all(c.status == CandidateStatus.DISCOVERED for c in saved)
    assert saved[0].name == "Noleak"
    assert saved[0].rank == 1
    assert saved[0].category == "TOP 10 Artificial Intelligence 2025"


@pytest.mark.anyio
async def test_name_hub_enrich_and_autosubmit_high_confidence():
    run_repo = FakeDiscoveryRunRepository()
    cand_repo = FakeCandidateRepository()
    submitter = FakeUrlSubmitter()
    items = [
        DiscoveredCandidateItem(name="Noleak", rank=1),
        DiscoveredCandidateItem(name="NeuralMind", rank=9),
    ]
    enricher = FakeEnricher(confidence=0.90)

    use_case = RunStartupDiscovery(
        uow_factory=make_uow_factory(run_repo, cand_repo),
        extractors={},
        name_extractors=_name_hub_extractors(items),
        url_ingestion_submitter=submitter,
        candidate_enricher=enricher,
        max_per_run=20,
    )

    view = await use_case.execute()

    assert view.status == DiscoveryRunStatus.COMPLETED
    assert view.candidates_discovered == 2
    assert view.candidates_enriched == 2
    assert view.jobs_submitted == 2
    assert len(submitter.submitted) == 2
    assert "noleak" in submitter.submitted[0]

    submitted_candidates = [
        c for c in cand_repo.candidates.values()
        if c.status == CandidateStatus.SUBMITTED
    ]
    assert len(submitted_candidates) == 2
    assert all(c.url_ingestion_job_id is not None for c in submitted_candidates)


@pytest.mark.anyio
async def test_name_hub_low_confidence_candidate_rejected_not_submitted():
    run_repo = FakeDiscoveryRunRepository()
    cand_repo = FakeCandidateRepository()
    submitter = FakeUrlSubmitter()
    items = [
        DiscoveredCandidateItem(name="Noleak", rank=1),
        DiscoveredCandidateItem(name="Ambiguous", rank=2),
    ]
    enricher = FakeEnricher(confidence=0.90, skip_names={"Ambiguous"})

    use_case = RunStartupDiscovery(
        uow_factory=make_uow_factory(run_repo, cand_repo),
        extractors={},
        name_extractors=_name_hub_extractors(items),
        url_ingestion_submitter=submitter,
        candidate_enricher=enricher,
        max_per_run=20,
    )

    view = await use_case.execute()

    assert view.jobs_submitted == 1
    assert len(submitter.submitted) == 1
    rejected = [
        c for c in cand_repo.candidates.values() if c.status == CandidateStatus.REJECTED
    ]
    assert len(rejected) == 1
    assert rejected[0].name == "Ambiguous"


@pytest.mark.anyio
async def test_name_hub_rejects_consultancy_candidate_before_enrichment():
    run_repo = FakeDiscoveryRunRepository()
    cand_repo = FakeCandidateRepository()
    submitter = FakeUrlSubmitter()
    items = [
        DiscoveredCandidateItem(
            name="inQuesti Consultoria",
            description="Consultoria de dados e servicos de analytics para empresas.",
            rank=1,
        ),
        DiscoveredCandidateItem(
            name="Produto AI",
            description="Plataforma SaaS de inteligencia artificial para operacoes.",
            rank=2,
        ),
    ]
    enricher = FakeEnricher(confidence=0.90)

    use_case = RunStartupDiscovery(
        uow_factory=make_uow_factory(run_repo, cand_repo),
        extractors={},
        name_extractors=_name_hub_extractors(items),
        url_ingestion_submitter=submitter,
        candidate_enricher=enricher,
        max_per_run=20,
    )

    view = await use_case.execute()

    assert view.jobs_submitted == 1
    assert submitter.submitted == ["https://produtoai.com"]
    rejected = [
        c for c in cand_repo.candidates.values() if c.status == CandidateStatus.REJECTED
    ]
    assert len(rejected) == 1
    assert rejected[0].name == "inQuesti Consultoria"
    assert rejected[0].rejection_reason == "consultancy_or_service_provider"


@pytest.mark.anyio
async def test_name_hub_failure_falls_back_gracefully():
    run_repo = FakeDiscoveryRunRepository()
    cand_repo = FakeCandidateRepository()

    name_mode_type = next(h.extractor_type for h in HUB_SOURCES if h.extraction_mode == "name")
    url_types = {h.extractor_type for h in HUB_SOURCES if h.extraction_mode == "url"}

    use_case = RunStartupDiscovery(
        uow_factory=make_uow_factory(run_repo, cand_repo),
        extractors={t: FakeUrlExtractor() for t in url_types},
        name_extractors={name_mode_type: FailingNameExtractor()},
        url_ingestion_submitter=FakeUrlSubmitter(),
        candidate_enricher=None,
        max_per_run=20,
    )

    view = await use_case.execute()

    assert view.status == DiscoveryRunStatus.COMPLETED
    assert view.candidates_discovered == 0


@pytest.mark.anyio
async def test_name_hub_normalized_name_computed_correctly():
    run_repo = FakeDiscoveryRunRepository()
    cand_repo = FakeCandidateRepository()
    items = [DiscoveredCandidateItem(name="PX Data.ai", rank=2)]

    use_case = RunStartupDiscovery(
        uow_factory=make_uow_factory(run_repo, cand_repo),
        extractors={},
        name_extractors=_name_hub_extractors(items),
        url_ingestion_submitter=FakeUrlSubmitter(),
        candidate_enricher=None,
        max_per_run=20,
    )

    await use_case.execute()

    candidates = list(cand_repo.candidates.values())
    assert len(candidates) == 1
    assert candidates[0].normalized_name == "pxdataai"


def test_candidate_entity_status_transitions():
    candidate = StartupDiscoveryCandidate(
        run_id=uuid4(),
        name="Noleak",
        normalized_name="noleak",
        discovery_source="100 Open Startups",
        discovery_source_url="https://example.com",
    )
    assert candidate.status == CandidateStatus.DISCOVERED

    candidate.enrich(
        official_website_url="https://noleak.com",
        official_site_confidence=0.90,
        enrichment_sources=["https://noleak.com"],
    )
    assert candidate.status == CandidateStatus.ENRICHED
    assert candidate.official_website_url == "https://noleak.com"

    job_id = uuid4()
    candidate.mark_submitted(job_id)
    assert candidate.status == CandidateStatus.SUBMITTED
    assert candidate.url_ingestion_job_id == job_id


def test_candidate_entity_reject_transition():
    candidate = StartupDiscoveryCandidate(
        run_id=uuid4(),
        name="Unknown",
        normalized_name="unknown",
        discovery_source="hub",
        discovery_source_url="https://hub.example",
    )
    candidate.reject("confidence_below_threshold")
    assert candidate.status == CandidateStatus.REJECTED
    assert "confidence_below_threshold" in candidate.rejection_reason
