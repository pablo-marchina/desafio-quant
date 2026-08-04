"""Testes da Orchestration V2 URL ingestion."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.orchestration.application.dto import (
    CreateUrlIngestionJobInput,
    ListUrlIngestionJobsInput,
)
from apps.api.src.modules.orchestration.application.ports import (
    BriefingPort,
    DocumentContentView,
    EmbeddingsPort,
    EnrichmentSearchCandidate,
    EnrichmentSearchExecutorPort,
    EnrichmentSearchPlannerPort,
    IngestionPort,
    RecommendationsPort,
    ScrapingPort,
    StartupExtractionAttempt,
    StartupProfileSnapshot,
    StartupsPort,
    StepStatus,
    UrlIngestionTaskDispatcher,
)
from apps.api.src.modules.orchestration.application.unit_of_work import (
    AnalysisUnitOfWork,
)
from apps.api.src.modules.orchestration.application.use_cases.advance_url_ingestion_job import (
    AdvanceUrlIngestionJob,
)
from apps.api.src.modules.orchestration.application.use_cases.create_url_ingestion_job import (
    CreateUrlIngestionJob,
)
from apps.api.src.modules.orchestration.application.use_cases.list_url_ingestion_jobs import (
    ListUrlIngestionJobs,
)
from apps.api.src.modules.orchestration.domain.entities import UrlIngestionJob
from apps.api.src.modules.orchestration.domain.enums import UrlIngestionJobStatus
from apps.api.src.modules.orchestration.domain.exceptions import (
    UrlIngestionStillProcessingError,
)
from apps.api.src.modules.orchestration.domain.repositories import (
    AnalysisJobRepository,
    UrlIngestionJobRepository,
)


class EmptyAnalysisJobRepository(AnalysisJobRepository):
    async def save(self, analysis_job) -> None:
        pass

    async def get_by_id(self, analysis_job_id: UUID):
        return None

    async def list_by_startup_id(self, startup_id: UUID) -> list:
        return []


class FakeUrlIngestionJobRepository(UrlIngestionJobRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, UrlIngestionJob] = {}

    async def save(self, job: UrlIngestionJob) -> None:
        self.items[job.id] = job

    async def get_by_id(self, job_id: UUID) -> UrlIngestionJob | None:
        return self.items.get(job_id)

    async def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: UrlIngestionJobStatus | None = None,
        source_type: str | None = None,
    ) -> tuple[list[UrlIngestionJob], int]:
        jobs = list(self.items.values())
        if status is not None:
            jobs = [job for job in jobs if job.status is status]
        if source_type:
            jobs = [job for job in jobs if job.source_type == source_type]
        jobs.sort(key=lambda job: (job.created_at, job.id), reverse=True)
        total = len(jobs)
        start = (page - 1) * page_size
        return jobs[start : start + page_size], total

    async def list_completed_by_url(self, url: str) -> list[UrlIngestionJob]:
        jobs = [
            job
            for job in self.items.values()
            if job.url == url and job.status is UrlIngestionJobStatus.COMPLETED
        ]
        jobs.sort(key=lambda job: job.created_at, reverse=True)
        return jobs

    async def list_by_startup_id(self, startup_id: UUID) -> list[UrlIngestionJob]:
        jobs = [job for job in self.items.values() if job.startup_id == startup_id]
        jobs.sort(key=lambda job: (job.created_at, job.id), reverse=True)
        return jobs


class FakeUoW(AnalysisUnitOfWork):
    def __init__(self, repository: FakeUrlIngestionJobRepository) -> None:
        self.analysis_job_repository = EmptyAnalysisJobRepository()
        self.url_ingestion_job_repository = repository

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
        pass

    async def rollback(self) -> None:
        pass


class FakeDispatcher(UrlIngestionTaskDispatcher):
    def __init__(self) -> None:
        self.dispatched_job_ids: list[UUID] = []

    async def dispatch(self, *, job_id: UUID) -> None:
        self.dispatched_job_ids.append(job_id)


class FakeScrapingPort(ScrapingPort):
    def __init__(
        self,
        status: StepStatus | None = None,
        html: str | None = None,
    ) -> None:
        self.submitted_urls: list[str] = []
        self.submitted_source_types: list[str] = []
        self.job_id = uuid4()
        self.status = status
        self._html = html

    async def submit(self, url: str, *, source_type: str = "startup_evidence") -> UUID:
        self.submitted_urls.append(url)
        self.submitted_source_types.append(source_type)
        return self.job_id

    async def get_status(self, job_id: UUID) -> StepStatus:
        assert self.status is not None
        return self.status

    async def get_html(self, result_id: UUID) -> str | None:
        return self._html


class FakeIngestionPort(IngestionPort):
    def __init__(
        self,
        *,
        status: StepStatus | None = None,
        content: DocumentContentView | None = None,
    ) -> None:
        self.submissions: list[tuple[UUID, str]] = []
        self.job_id = uuid4()
        self._status = status
        self._content = content

    async def submit(
        self,
        scraping_result_id: UUID,
        *,
        source_type: str = "startup_evidence",
    ) -> UUID:
        self.submissions.append((scraping_result_id, source_type))
        return self.job_id

    async def get_status(self, job_id: UUID) -> StepStatus:
        if self._status is not None:
            return self._status
        return StepStatus(
            is_done=False,
            is_failed=False,
            result_id=None,
            error_message=None,
        )

    async def get_document_content(
        self, scraping_result_id: UUID
    ) -> DocumentContentView | None:
        return self._content


class FakeEmbeddingsPort(EmbeddingsPort):
    def __init__(self, status: StepStatus | None = None) -> None:
        self._status = status
        self.deleted_document_ids: list[UUID] = []

    async def submit(self, document_id: UUID) -> UUID:
        return uuid4()

    async def get_status(self, job_id: UUID) -> StepStatus:
        if self._status is not None:
            return self._status
        return StepStatus(
            is_done=False,
            is_failed=False,
            result_id=None,
            error_message=None,
        )

    async def delete_vectors_for_document(self, document_id: UUID) -> None:
        self.deleted_document_ids.append(document_id)


class FakeStartupsPort(StartupsPort):
    def __init__(
        self,
        *,
        startup_id: UUID | None = None,
        profile: StartupProfileSnapshot | None = None,
        extraction_attempt: StartupExtractionAttempt | None = None,
    ) -> None:
        self.created: list[tuple[str, str]] = []
        self.attached: list[tuple[UUID, UUID, str, str | None, str | None]] = []
        self.try_extract_calls: list[UUID] = []
        self.try_classify_calls: list[UUID] = []
        self._startup_id = startup_id or uuid4()
        self._profile = profile
        self._extraction_attempt = extraction_attempt or StartupExtractionAttempt(
            succeeded=True
        )

    async def create_startup(self, *, name: str, website_url: str) -> UUID:
        self.created.append((name, website_url))
        return self._startup_id

    async def attach_evidence(
        self,
        *,
        startup_id: UUID,
        scraping_result_id: UUID,
        source_url: str,
        title: str | None,
        notes: str | None,
    ) -> None:
        self.attached.append(
            (startup_id, scraping_result_id, source_url, title, notes)
        )

    async def try_extract(self, startup_id: UUID) -> StartupExtractionAttempt:
        self.try_extract_calls.append(startup_id)
        return self._extraction_attempt

    async def try_classify(self, startup_id: UUID) -> None:
        self.try_classify_calls.append(startup_id)

    async def get_profile(self, startup_id: UUID) -> StartupProfileSnapshot:
        if self._profile is not None:
            return self._profile
        return StartupProfileSnapshot(
            name="Acme AI",
            website_url="https://acme.example.com",
            founders=["Ada Lovelace"],
            funding_stage="seed",
            customers=["Contoso"],
            evidence_urls=[],
            ai_workload_type="nlp",
            deployment_stage="production",
            gpu_need="high",
        )


class FakeRecommendationsPort(RecommendationsPort):
    def __init__(self, *, count: int = 0, error: Exception | None = None) -> None:
        self.calls: list[UUID] = []
        self._count = count
        self._error = error

    async def generate(self, startup_id: UUID) -> int:
        self.calls.append(startup_id)
        if self._error is not None:
            raise self._error
        return self._count


class FakeBriefingPort(BriefingPort):
    def __init__(self, *, briefing_id: UUID | None = None) -> None:
        self.calls: list[UUID] = []
        self._briefing_id = briefing_id or uuid4()

    async def generate(self, startup_id: UUID) -> UUID:
        self.calls.append(startup_id)
        return self._briefing_id


class FakeEnrichmentSearchPlannerPort(EnrichmentSearchPlannerPort):
    def __init__(self, queries: list[str] | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._queries = (
            ["acme founders funding customers"] if queries is None else queries
        )

    async def plan_queries(
        self,
        *,
        startup_name: str,
        source_url: str,
        source_title: str | None,
        raw_text: str,
        missing_signals: list[str],
        known_terms: list[str],
        excluded_urls: list[str],
        max_queries: int = 3,
    ) -> list[str]:
        self.calls.append(
            {
                "startup_name": startup_name,
                "source_url": source_url,
                "source_title": source_title,
                "raw_text": raw_text,
                "missing_signals": missing_signals,
                "known_terms": known_terms,
                "excluded_urls": excluded_urls,
                "max_queries": max_queries,
            }
        )
        return self._queries


class FakeEnrichmentSearchExecutorPort(EnrichmentSearchExecutorPort):
    def __init__(self, results: list[EnrichmentSearchCandidate]) -> None:
        self.calls: list[tuple[str, list[str], int]] = []
        self._results = results

    async def search(
        self,
        query: str,
        *,
        excluded_urls: list[str],
        max_results: int = 2,
    ) -> list[EnrichmentSearchCandidate]:
        self.calls.append((query, excluded_urls, max_results))
        return self._results


def _make_advance_use_case(
    *,
    repository: FakeUrlIngestionJobRepository,
    scraping_port: ScrapingPort | None = None,
    ingestion_port: IngestionPort | None = None,
    embeddings_port: EmbeddingsPort | None = None,
    startups_port: StartupsPort | None = None,
    recommendations_port: RecommendationsPort | None = None,
    briefing_port: BriefingPort | None = None,
    task_dispatcher: UrlIngestionTaskDispatcher | None = None,
    search_planner_port: EnrichmentSearchPlannerPort | None = None,
    search_executor_port: EnrichmentSearchExecutorPort | None = None,
) -> AdvanceUrlIngestionJob:
    return AdvanceUrlIngestionJob(
        uow_factory=lambda: FakeUoW(repository),
        scraping_port=scraping_port or FakeScrapingPort(),
        ingestion_port=ingestion_port or FakeIngestionPort(),
        embeddings_port=embeddings_port or FakeEmbeddingsPort(),
        startups_port=startups_port or FakeStartupsPort(),
        recommendations_port=recommendations_port or FakeRecommendationsPort(),
        briefing_port=briefing_port or FakeBriefingPort(),
        task_dispatcher=task_dispatcher or FakeDispatcher(),
        search_planner_port=search_planner_port,
        search_executor_port=search_executor_port,
    )


@pytest.mark.anyio
async def test_create_url_ingestion_job_persists_source_type_and_dispatches() -> None:
    repository = FakeUrlIngestionJobRepository()
    dispatcher = FakeDispatcher()
    use_case = CreateUrlIngestionJob(lambda: FakeUoW(repository), dispatcher)

    view = await use_case.execute(
        CreateUrlIngestionJobInput(
            url="https://docs.nvidia.com/nim/",
            source_type="nvidia_knowledge",
        )
    )

    assert view.status is UrlIngestionJobStatus.PENDING
    assert view.source_type == "nvidia_knowledge"
    assert dispatcher.dispatched_job_ids == [view.id]
    assert repository.items[view.id].source_type == "nvidia_knowledge"


@pytest.mark.anyio
async def test_advance_uses_job_source_type_when_submitting_scraping() -> None:
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(
        url="https://docs.nvidia.com/nim/",
        source_type="nvidia_knowledge",
    )
    await repository.save(job)
    scraping_port = FakeScrapingPort()
    use_case = _make_advance_use_case(
        repository=repository, scraping_port=scraping_port
    )

    with pytest.raises(UrlIngestionStillProcessingError):
        await use_case.execute(job_id=job.id)

    assert scraping_port.submitted_urls == ["https://docs.nvidia.com/nim/"]
    assert scraping_port.submitted_source_types == ["nvidia_knowledge"]
    assert repository.items[job.id].status is UrlIngestionJobStatus.SCRAPING


@pytest.mark.anyio
async def test_advance_uses_job_source_type_when_submitting_ingestion() -> None:
    scraping_result_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(
        url="https://docs.nvidia.com/nim/",
        source_type="nvidia_knowledge",
    )
    job.start_scraping(uuid4())
    await repository.save(job)
    ingestion_port = FakeIngestionPort()
    use_case = _make_advance_use_case(
        repository=repository,
        scraping_port=FakeScrapingPort(
            StepStatus(
                is_done=True,
                is_failed=False,
                result_id=scraping_result_id,
                error_message=None,
            )
        ),
        ingestion_port=ingestion_port,
    )

    with pytest.raises(UrlIngestionStillProcessingError):
        await use_case.execute(job_id=job.id)

    assert ingestion_port.submissions == [
        (scraping_result_id, "nvidia_knowledge")
    ]
    assert repository.items[job.id].status is UrlIngestionJobStatus.INGESTING


@pytest.mark.anyio
async def test_scraping_done_without_result_fails_job_instead_of_asserting() -> None:
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(
        url="https://docs.nvidia.com/nim/",
        source_type="nvidia_knowledge",
    )
    job.start_scraping(uuid4())
    await repository.save(job)
    ingestion_port = FakeIngestionPort()
    use_case = _make_advance_use_case(
        repository=repository,
        scraping_port=FakeScrapingPort(
            StepStatus(
                is_done=True,
                is_failed=False,
                result_id=None,
                error_message=None,
            )
        ),
        ingestion_port=ingestion_port,
    )

    await use_case.execute(job_id=job.id)

    saved = repository.items[job.id]
    assert saved.status is UrlIngestionJobStatus.FAILED
    assert saved.error_message == "Scraping concluiu sem scraping_result_id."
    assert ingestion_port.submissions == []


@pytest.mark.anyio
async def test_ingestion_done_without_result_fails_job_instead_of_asserting() -> None:
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(
        url="https://docs.nvidia.com/nim/",
        source_type="nvidia_knowledge",
    )
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    await repository.save(job)
    embeddings_port = FakeEmbeddingsPort()
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            status=StepStatus(
                is_done=True,
                is_failed=False,
                result_id=None,
                error_message=None,
            )
        ),
        embeddings_port=embeddings_port,
    )

    await use_case.execute(job_id=job.id)

    saved = repository.items[job.id]
    assert saved.status is UrlIngestionJobStatus.FAILED
    assert saved.error_message == "Ingestion concluiu sem document_id."


@pytest.mark.anyio
async def test_scraping_rejection_schedules_enrichment_instead_of_stopping_silently() -> None:
    startup_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(url="https://www.kunumi.com/")
    job.start_scraping(uuid4())
    await repository.save(job)
    dispatcher = FakeDispatcher()
    planner = FakeEnrichmentSearchPlannerPort(["Kunumi founders customers funding"])
    executor = FakeEnrichmentSearchExecutorPort(
        [
            EnrichmentSearchCandidate(url="https://www.crunchbase.com/organization/kunumi"),
            EnrichmentSearchCandidate(url="https://www.instagram.com/kunumilab"),
            EnrichmentSearchCandidate(url="https://grokipedia.com/page/Moradaai"),
        ]
    )
    startups_port = FakeStartupsPort(
        startup_id=startup_id,
        profile=StartupProfileSnapshot(
            name="kunumi.com",
            website_url="https://www.kunumi.com/",
            founders=[],
            funding_stage=None,
            customers=[],
            evidence_urls=[],
        ),
    )
    use_case = _make_advance_use_case(
        repository=repository,
        scraping_port=FakeScrapingPort(
            StepStatus(
                is_done=False,
                is_failed=True,
                result_id=None,
                error_message="O conteúdo coletado foi rejeitado pela validação.",
            )
        ),
        startups_port=startups_port,
        task_dispatcher=dispatcher,
        search_planner_port=planner,
        search_executor_port=executor,
    )

    await use_case.execute(job_id=job.id)

    saved = repository.items[job.id]
    enrichment_jobs = [
        item for item in repository.items.values() if item.parent_job_id == job.id
    ]
    assert saved.status is UrlIngestionJobStatus.FAILED
    assert saved.startup_id == startup_id
    assert startups_port.created == [("Kunumi", "https://www.kunumi.com/")]
    assert [item.url for item in enrichment_jobs] == [
        "https://www.kunumi.com/sobre",
        "https://www.crunchbase.com/organization/kunumi",
    ]
    assert dispatcher.dispatched_job_ids == [item.id for item in enrichment_jobs]


@pytest.mark.anyio
async def test_embedding_completion_completes_directly_for_nvidia_knowledge() -> None:
    """Nao-regressao: fontes curadas (nvidia_knowledge) nunca viram 'startup'."""

    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(
        url="https://docs.nvidia.com/nim/",
        source_type="nvidia_knowledge",
    )
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    await repository.save(job)
    startups_port = FakeStartupsPort()
    use_case = _make_advance_use_case(
        repository=repository,
        embeddings_port=FakeEmbeddingsPort(
            StepStatus(
                is_done=True, is_failed=False, result_id=None, error_message=None
            )
        ),
        startups_port=startups_port,
    )

    await use_case.execute(job_id=job.id)

    assert repository.items[job.id].status is UrlIngestionJobStatus.COMPLETED
    assert startups_port.created == []


@pytest.mark.anyio
async def test_embedding_completion_starts_analyzing_for_startup_evidence() -> None:
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(url="https://acme.example.com")
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    await repository.save(job)
    use_case = _make_advance_use_case(
        repository=repository,
        embeddings_port=FakeEmbeddingsPort(
            StepStatus(
                is_done=True, is_failed=False, result_id=None, error_message=None
            )
        ),
    )

    with pytest.raises(UrlIngestionStillProcessingError):
        await use_case.execute(job_id=job.id)

    assert repository.items[job.id].status is UrlIngestionJobStatus.ANALYZING


@pytest.mark.anyio
async def test_embedding_completion_deletes_vectors_of_previous_completed_job_with_same_url() -> (
    None
):
    """Re-scrape (cache de 3 dias expirado) nao deve deixar vetor orfao."""

    repository = FakeUrlIngestionJobRepository()
    url = "https://acme.example.com"

    old_document_id = uuid4()
    old_job = UrlIngestionJob(url=url)
    old_job.start_scraping(uuid4())
    old_job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    old_job.start_embedding(document_id=old_document_id, embedding_job_id=uuid4())
    old_job.complete()
    await repository.save(old_job)

    new_document_id = uuid4()
    new_job = UrlIngestionJob(url=url)
    new_job.start_scraping(uuid4())
    new_job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    new_job.start_embedding(document_id=new_document_id, embedding_job_id=uuid4())
    await repository.save(new_job)

    embeddings_port = FakeEmbeddingsPort(
        StepStatus(is_done=True, is_failed=False, result_id=None, error_message=None)
    )
    use_case = _make_advance_use_case(
        repository=repository, embeddings_port=embeddings_port
    )

    with pytest.raises(UrlIngestionStillProcessingError):
        await use_case.execute(job_id=new_job.id)

    assert embeddings_port.deleted_document_ids == [old_document_id]


@pytest.mark.anyio
async def test_embedding_completion_skips_cleanup_without_previous_completed_job() -> (
    None
):
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(url="https://acme.example.com")
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    await repository.save(job)
    embeddings_port = FakeEmbeddingsPort(
        StepStatus(is_done=True, is_failed=False, result_id=None, error_message=None)
    )
    use_case = _make_advance_use_case(
        repository=repository, embeddings_port=embeddings_port
    )

    with pytest.raises(UrlIngestionStillProcessingError):
        await use_case.execute(job_id=job.id)

    assert embeddings_port.deleted_document_ids == []


@pytest.mark.anyio
async def test_analyzing_creates_startup_with_document_title_when_no_startup_id() -> (
    None
):
    scraping_result_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(url="https://acme.example.com")
    job.start_scraping(uuid4())
    job.start_ingesting(
        scraping_result_id=scraping_result_id, ingestion_job_id=uuid4()
    )
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    await repository.save(job)
    startups_port = FakeStartupsPort()
    recommendations_port = FakeRecommendationsPort(count=2)
    briefing_id = uuid4()
    briefing_port = FakeBriefingPort(briefing_id=briefing_id)
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo " * 10)
        ),
        startups_port=startups_port,
        recommendations_port=recommendations_port,
        briefing_port=briefing_port,
    )

    await use_case.execute(job_id=job.id)

    saved = repository.items[job.id]
    assert saved.status is UrlIngestionJobStatus.COMPLETED
    assert startups_port.created == [("Acme AI", "https://acme.example.com")]
    assert saved.startup_id == startups_port._startup_id
    assert saved.evidence_attached is True
    assert len(startups_port.attached) == 1
    assert startups_port.try_extract_calls == [startups_port._startup_id]
    assert startups_port.try_classify_calls == [startups_port._startup_id]
    assert recommendations_port.calls == [startups_port._startup_id]
    assert briefing_port.calls == [startups_port._startup_id]
    assert saved.recommendation_count == 2
    assert saved.briefing_id == briefing_id


@pytest.mark.anyio
async def test_analyzing_schedules_enrichment_jobs_when_profile_is_incomplete() -> None:
    startup_id = uuid4()
    scraping_result_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(url="https://acme.example.com", startup_id=startup_id)
    job.start_scraping(uuid4())
    job.start_ingesting(
        scraping_result_id=scraping_result_id, ingestion_job_id=uuid4()
    )
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    await repository.save(job)
    dispatcher = FakeDispatcher()
    startups_port = FakeStartupsPort(
        startup_id=startup_id,
        profile=StartupProfileSnapshot(
            name="Acme AI",
            website_url="https://acme.example.com",
            founders=[],
            funding_stage=None,
            customers=[],
            evidence_urls=["https://acme.example.com"],
        ),
    )
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        startups_port=startups_port,
        task_dispatcher=dispatcher,
    )

    with pytest.raises(UrlIngestionStillProcessingError):
        await use_case.execute(job_id=job.id)

    enrichment_jobs = [
        item for item in repository.items.values() if item.parent_job_id == job.id
    ]
    assert [item.url for item in enrichment_jobs] == [
        "https://acme.example.com/sobre",
        "https://acme.example.com/about",
        "https://acme.example.com/blog",
        "https://acme.example.com/carreiras",
    ]
    assert {item.startup_id for item in enrichment_jobs} == {startup_id}
    assert {item.enrichment_round for item in enrichment_jobs} == {1}
    assert dispatcher.dispatched_job_ids == [item.id for item in enrichment_jobs]
    assert repository.items[job.id].status is UrlIngestionJobStatus.ANALYZING


@pytest.mark.anyio
async def test_analyzing_defers_recommendations_when_enrichment_is_scheduled() -> None:
    startup_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(url="https://acme.example.com", startup_id=startup_id)
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    await repository.save(job)
    recommendations_port = FakeRecommendationsPort(count=2)
    briefing_port = FakeBriefingPort()
    startups_port = FakeStartupsPort(
        startup_id=startup_id,
        profile=StartupProfileSnapshot(
            name="Acme AI",
            website_url="https://acme.example.com",
            founders=[],
            funding_stage=None,
            customers=[],
            evidence_urls=["https://acme.example.com"],
        ),
    )
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        startups_port=startups_port,
        recommendations_port=recommendations_port,
        briefing_port=briefing_port,
    )

    with pytest.raises(UrlIngestionStillProcessingError):
        await use_case.execute(job_id=job.id)

    assert recommendations_port.calls == []
    assert briefing_port.calls == []
    assert repository.items[job.id].status is UrlIngestionJobStatus.ANALYZING
    assert repository.items[job.id].recommendations_done is False


@pytest.mark.anyio
async def test_analyzing_prefers_external_search_candidates_when_configured() -> None:
    startup_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(url="https://acme.example.com", startup_id=startup_id)
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    await repository.save(job)
    planner = FakeEnrichmentSearchPlannerPort()
    executor = FakeEnrichmentSearchExecutorPort(
        [
            EnrichmentSearchCandidate(url="https://acme.example.com/team"),
            EnrichmentSearchCandidate(url="https://news.example.com/acme-seed"),
            EnrichmentSearchCandidate(url="https://www.instagram.com/acme-ai"),
            EnrichmentSearchCandidate(url="https://www.linkedin.com/company/acme-ai/"),
        ]
    )
    startups_port = FakeStartupsPort(
        startup_id=startup_id,
        profile=StartupProfileSnapshot(
            name="Acme AI",
            website_url="https://acme.example.com",
            founders=[],
            funding_stage=None,
            customers=[],
            evidence_urls=["https://acme.example.com"],
        ),
    )
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(
                title="Acme AI",
                clean_text="landing page with weak evidence",
            )
        ),
        startups_port=startups_port,
        search_planner_port=planner,
        search_executor_port=executor,
    )

    with pytest.raises(UrlIngestionStillProcessingError):
        await use_case.execute(job_id=job.id)

    enrichment_jobs = [
        item for item in repository.items.values() if item.parent_job_id == job.id
    ]
    assert [item.url for item in enrichment_jobs] == [
        "https://acme.example.com/sobre",
        "https://www.linkedin.com/company/acme-ai",
        "https://news.example.com/acme-seed",
        "https://acme.example.com/team",
    ]
    assert planner.calls[0]["missing_signals"] == [
        "ai_workload_type",
        "deployment_stage",
        "gpu_need",
        "founders",
        "funding_stage",
        "customers",
    ]
    assert (
        executor.calls[0][0]
        == '"Acme AI" startup IA notícia lançamento investimento rodada'
    )


@pytest.mark.anyio
async def test_analyzing_uses_deterministic_queries_when_planner_is_empty() -> None:
    startup_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(url="https://acme.example.com", startup_id=startup_id)
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    await repository.save(job)
    planner = FakeEnrichmentSearchPlannerPort([])
    executor = FakeEnrichmentSearchExecutorPort(
        [
            EnrichmentSearchCandidate(
                url="https://www.crunchbase.com/organization/acme-ai"
            ),
        ]
    )
    startups_port = FakeStartupsPort(
        startup_id=startup_id,
        profile=StartupProfileSnapshot(
            name="Acme AI",
            website_url="https://acme.example.com",
            founders=[],
            funding_stage=None,
            customers=[],
            evidence_urls=["https://acme.example.com"],
        ),
    )
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="")
        ),
        startups_port=startups_port,
        search_planner_port=planner,
        search_executor_port=executor,
    )

    with pytest.raises(UrlIngestionStillProcessingError):
        await use_case.execute(job_id=job.id)

    enrichment_jobs = [
        item for item in repository.items.values() if item.parent_job_id == job.id
    ]
    assert [item.url for item in enrichment_jobs] == [
        "https://acme.example.com/sobre",
        "https://www.crunchbase.com/organization/acme-ai",
    ]
    assert (
        executor.calls[0][0]
        == '"Acme AI" startup IA notícia lançamento investimento rodada'
    )
    assert executor.calls[0][2] == 5


@pytest.mark.anyio
async def test_analyzing_does_not_schedule_enrichment_when_profile_is_complete() -> None:
    startup_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(url="https://acme.example.com", startup_id=startup_id)
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    await repository.save(job)
    dispatcher = FakeDispatcher()
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        startups_port=FakeStartupsPort(startup_id=startup_id),
        task_dispatcher=dispatcher,
    )

    await use_case.execute(job_id=job.id)

    assert [
        item for item in repository.items.values() if item.parent_job_id == job.id
    ] == []
    assert dispatcher.dispatched_job_ids == []


@pytest.mark.anyio
async def test_enrichment_child_requeues_parent_without_scheduling_new_children() -> None:
    startup_id = uuid4()
    parent_job_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(
        url="https://acme.example.com/about",
        startup_id=startup_id,
        parent_job_id=parent_job_id,
        enrichment_round=1,
    )
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    await repository.save(job)
    dispatcher = FakeDispatcher()
    startups_port = FakeStartupsPort(
        startup_id=startup_id,
        profile=StartupProfileSnapshot(
            name="Acme AI",
            website_url="https://acme.example.com",
            founders=[],
            funding_stage=None,
            customers=[],
            evidence_urls=[],
        ),
    )
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        startups_port=startups_port,
        task_dispatcher=dispatcher,
    )

    await use_case.execute(job_id=job.id)

    assert dispatcher.dispatched_job_ids == [parent_job_id]
    assert [
        item for item in repository.items.values() if item.parent_job_id == job.id
    ] == []


@pytest.mark.anyio
async def test_parent_job_waits_for_active_enrichment_children_before_final_analysis() -> None:
    startup_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(
        url="https://acme.example.com",
        startup_id=startup_id,
    )
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    job.mark_evidence_attached()
    await repository.save(job)
    active_child = UrlIngestionJob(
        url="https://acme.example.com/about",
        startup_id=startup_id,
        parent_job_id=job.id,
        enrichment_round=1,
    )
    await repository.save(active_child)
    startups_port = FakeStartupsPort(startup_id=startup_id)
    recommendations_port = FakeRecommendationsPort(count=2)
    briefing_port = FakeBriefingPort()
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        startups_port=startups_port,
        recommendations_port=recommendations_port,
        briefing_port=briefing_port,
    )

    with pytest.raises(UrlIngestionStillProcessingError):
        await use_case.execute(job_id=job.id)

    assert startups_port.try_extract_calls == []
    assert startups_port.try_classify_calls == []
    assert recommendations_port.calls == []
    assert briefing_port.calls == []
    assert repository.items[job.id].status is UrlIngestionJobStatus.ANALYZING


@pytest.mark.anyio
async def test_parent_job_completes_collected_enrichment_child_before_final_analysis() -> None:
    startup_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(
        url="https://acme.example.com",
        startup_id=startup_id,
    )
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    job.mark_evidence_attached()
    await repository.save(job)
    collected_child = UrlIngestionJob(
        url="https://acme.example.com/about",
        startup_id=startup_id,
        parent_job_id=job.id,
        enrichment_round=1,
    )
    collected_child.start_scraping(uuid4())
    collected_child.start_ingesting(
        scraping_result_id=uuid4(), ingestion_job_id=uuid4()
    )
    collected_child.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    collected_child.start_analyzing()
    collected_child.mark_evidence_attached()
    await repository.save(collected_child)
    startups_port = FakeStartupsPort(startup_id=startup_id)
    recommendations_port = FakeRecommendationsPort(count=2)
    briefing_port = FakeBriefingPort()
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        startups_port=startups_port,
        recommendations_port=recommendations_port,
        briefing_port=briefing_port,
    )

    await use_case.execute(job_id=job.id)

    assert repository.items[collected_child.id].status is UrlIngestionJobStatus.COMPLETED
    assert repository.items[job.id].status is UrlIngestionJobStatus.COMPLETED
    assert recommendations_port.calls == [startup_id]
    assert briefing_port.calls == [startup_id]


@pytest.mark.anyio
async def test_parent_job_runs_consolidated_analysis_when_enrichment_children_are_terminal() -> None:
    startup_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(
        url="https://acme.example.com",
        startup_id=startup_id,
    )
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    job.mark_evidence_attached()
    await repository.save(job)
    completed_child = UrlIngestionJob(
        url="https://acme.example.com/about",
        startup_id=startup_id,
        parent_job_id=job.id,
        enrichment_round=1,
    )
    completed_child.start_scraping(uuid4())
    completed_child.start_ingesting(
        scraping_result_id=uuid4(), ingestion_job_id=uuid4()
    )
    completed_child.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    completed_child.start_analyzing()
    completed_child.complete()
    await repository.save(completed_child)
    startups_port = FakeStartupsPort(startup_id=startup_id)
    recommendations_port = FakeRecommendationsPort(count=2)
    briefing_port = FakeBriefingPort()
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        startups_port=startups_port,
        recommendations_port=recommendations_port,
        briefing_port=briefing_port,
    )

    await use_case.execute(job_id=job.id)

    assert startups_port.try_extract_calls == [startup_id]
    assert startups_port.try_classify_calls == [startup_id]
    assert recommendations_port.calls == [startup_id]
    assert briefing_port.calls == [startup_id]
    assert repository.items[job.id].status is UrlIngestionJobStatus.COMPLETED


@pytest.mark.anyio
async def test_parent_job_fails_without_recommendations_when_profile_stays_unstructured() -> None:
    startup_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(
        url="https://acme.example.com",
        startup_id=startup_id,
    )
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    job.mark_evidence_attached()
    await repository.save(job)
    completed_child = UrlIngestionJob(
        url="https://acme.example.com/about",
        startup_id=startup_id,
        parent_job_id=job.id,
        enrichment_round=1,
    )
    completed_child.start_scraping(uuid4())
    completed_child.start_ingesting(
        scraping_result_id=uuid4(), ingestion_job_id=uuid4()
    )
    completed_child.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    completed_child.start_analyzing()
    completed_child.complete()
    await repository.save(completed_child)
    startups_port = FakeStartupsPort(
        startup_id=startup_id,
        profile=StartupProfileSnapshot(
            name="Acme AI",
            website_url="https://acme.example.com",
            founders=[],
            funding_stage=None,
            customers=[],
            evidence_urls=["https://acme.example.com"],
            ai_workload_type="unknown",
            deployment_stage="unknown",
            gpu_need="unknown",
        ),
        extraction_attempt=StartupExtractionAttempt(
            succeeded=False,
            timed_out=True,
            error_message="timeout after 120s",
        ),
    )
    recommendations_port = FakeRecommendationsPort(count=2)
    briefing_port = FakeBriefingPort()
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        startups_port=startups_port,
        recommendations_port=recommendations_port,
        briefing_port=briefing_port,
    )

    await use_case.execute(job_id=job.id)

    saved = repository.items[job.id]
    assert saved.status is UrlIngestionJobStatus.FAILED
    assert "Perfil estruturado de IA incompleto" in (saved.error_message or "")
    assert "ai_workload_type" in (saved.error_message or "")
    assert recommendations_port.calls == []
    assert briefing_port.calls == []


@pytest.mark.anyio
async def test_parent_job_allows_recommendations_when_profile_has_minimum_ai_signal() -> None:
    startup_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(
        url="https://acme.example.com",
        startup_id=startup_id,
    )
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=uuid4(), ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    job.mark_evidence_attached()
    await repository.save(job)
    completed_child = UrlIngestionJob(
        url="https://acme.example.com/about",
        startup_id=startup_id,
        parent_job_id=job.id,
        enrichment_round=1,
    )
    completed_child.start_scraping(uuid4())
    completed_child.start_ingesting(
        scraping_result_id=uuid4(), ingestion_job_id=uuid4()
    )
    completed_child.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    completed_child.start_analyzing()
    completed_child.complete()
    await repository.save(completed_child)
    startups_port = FakeStartupsPort(
        startup_id=startup_id,
        profile=StartupProfileSnapshot(
            name="Acme AI",
            website_url="https://acme.example.com",
            founders=[],
            funding_stage=None,
            customers=[],
            evidence_urls=["https://acme.example.com"],
            ai_workload_type="analytics",
            deployment_stage="production",
            gpu_need="unknown",
        ),
        extraction_attempt=StartupExtractionAttempt(succeeded=True),
    )
    recommendations_port = FakeRecommendationsPort(count=2)
    briefing_port = FakeBriefingPort()
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        startups_port=startups_port,
        recommendations_port=recommendations_port,
        briefing_port=briefing_port,
    )

    await use_case.execute(job_id=job.id)

    assert repository.items[job.id].status is UrlIngestionJobStatus.COMPLETED
    assert recommendations_port.calls == [startup_id]
    assert briefing_port.calls == [startup_id]


@pytest.mark.anyio
async def test_analyzing_uses_hostname_when_document_has_no_title() -> None:
    scraping_result_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(url="https://www.acme.example.com/about")
    job.start_scraping(uuid4())
    job.start_ingesting(
        scraping_result_id=scraping_result_id, ingestion_job_id=uuid4()
    )
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    await repository.save(job)
    startups_port = FakeStartupsPort()
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title=None, clean_text="conteudo")
        ),
        startups_port=startups_port,
    )

    await use_case.execute(job_id=job.id)

    assert startups_port.created == [
        ("Example", "https://www.acme.example.com/about")
    ]


@pytest.mark.anyio
async def test_analyzing_skips_create_startup_when_startup_id_already_set() -> None:
    """Modo 'associar a startup existente': startup_id vem do input de criacao."""

    existing_startup_id = uuid4()
    scraping_result_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(
        url="https://acme.example.com", startup_id=existing_startup_id
    )
    job.start_scraping(uuid4())
    job.start_ingesting(
        scraping_result_id=scraping_result_id, ingestion_job_id=uuid4()
    )
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    await repository.save(job)
    startups_port = FakeStartupsPort()
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        startups_port=startups_port,
    )

    await use_case.execute(job_id=job.id)

    assert startups_port.created == []
    assert len(startups_port.attached) == 1
    assert startups_port.attached[0][0] == existing_startup_id
    assert repository.items[job.id].startup_id == existing_startup_id


@pytest.mark.anyio
async def test_analyzing_redelivery_skips_create_and_attach_but_reruns_rest() -> None:
    """Simula reentrega-por-crash: startup_id/evidence_attached ja persistidos."""

    existing_startup_id = uuid4()
    scraping_result_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(url="https://acme.example.com")
    job.start_scraping(uuid4())
    job.start_ingesting(
        scraping_result_id=scraping_result_id, ingestion_job_id=uuid4()
    )
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    job.link_startup(existing_startup_id)
    job.mark_evidence_attached()
    await repository.save(job)
    startups_port = FakeStartupsPort(startup_id=existing_startup_id)
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        startups_port=startups_port,
    )

    await use_case.execute(job_id=job.id)

    assert startups_port.created == []
    assert startups_port.attached == []
    assert startups_port.try_extract_calls == [existing_startup_id]
    assert startups_port.try_classify_calls == [existing_startup_id]
    assert repository.items[job.id].status is UrlIngestionJobStatus.COMPLETED


@pytest.mark.anyio
async def test_analyzing_fails_job_when_recommendations_port_raises() -> None:
    scraping_result_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(url="https://acme.example.com")
    job.start_scraping(uuid4())
    job.start_ingesting(
        scraping_result_id=scraping_result_id, ingestion_job_id=uuid4()
    )
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    await repository.save(job)
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        recommendations_port=FakeRecommendationsPort(
            error=RuntimeError("falha inesperada")
        ),
    )

    await use_case.execute(job_id=job.id)

    saved = repository.items[job.id]
    assert saved.status is UrlIngestionJobStatus.FAILED
    assert saved.error_message == "falha inesperada"


@pytest.mark.anyio
async def test_list_url_ingestion_jobs_filters_and_paginates_history() -> None:
    repository = FakeUrlIngestionJobRepository()
    matching = UrlIngestionJob(url="https://acme.example.com")
    matching.start_scraping(uuid4())
    other_status = UrlIngestionJob(url="https://beta.example.com")
    other_source = UrlIngestionJob(
        url="https://docs.nvidia.com/nim/", source_type="nvidia_knowledge"
    )
    other_source.start_scraping(uuid4())
    for job in (matching, other_status, other_source):
        await repository.save(job)

    page = await ListUrlIngestionJobs(lambda: FakeUoW(repository)).execute(
        ListUrlIngestionJobsInput(
            page=1,
            page_size=10,
            status=UrlIngestionJobStatus.SCRAPING,
            source_type="startup_evidence",
        )
    )

    assert page.total == 1
    assert page.items[0].id == matching.id


# ---------------------------------------------------------------------------
# DT-09: retry granular por sub-passo em ANALYZING
# ---------------------------------------------------------------------------


def test_record_recommendations_sets_done_flag() -> None:
    """record_recommendations() persiste o count e marca recommendations_done."""
    job = UrlIngestionJob(url="https://acme.example.com")
    assert job.recommendations_done is False
    assert job.recommendation_count is None

    job.record_recommendations(3)

    assert job.recommendations_done is True
    assert job.recommendation_count == 3


@pytest.mark.anyio
async def test_analyzing_saves_recommendations_done_before_briefing() -> None:
    """Apos recommendations.generate(), o job e salvo com recommendations_done=True."""
    scraping_result_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(url="https://acme.example.com")
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=scraping_result_id, ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    await repository.save(job)

    recs_port = FakeRecommendationsPort(count=2)
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        recommendations_port=recs_port,
    )

    await use_case.execute(job_id=job.id)

    saved = repository.items[job.id]
    assert saved.status is UrlIngestionJobStatus.COMPLETED
    assert saved.recommendations_done is True
    assert saved.recommendation_count == 2


@pytest.mark.anyio
async def test_analyzing_redelivery_skips_recommendations_when_done() -> None:
    """Retry com recommendations_done=True nao chama recommendations.generate() de novo."""
    scraping_result_id = uuid4()
    existing_startup_id = uuid4()
    repository = FakeUrlIngestionJobRepository()
    job = UrlIngestionJob(url="https://acme.example.com")
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=scraping_result_id, ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    job.link_startup(existing_startup_id)
    job.mark_evidence_attached()
    job.record_recommendations(5)  # simulando: recomendacoes ja concluidas
    await repository.save(job)

    recs_port = FakeRecommendationsPort(count=99)  # nunca deve ser chamado
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        startups_port=FakeStartupsPort(startup_id=existing_startup_id),
        recommendations_port=recs_port,
    )

    await use_case.execute(job_id=job.id)

    # recommendations.generate() nao foi chamado
    assert recs_port.calls == []
    # o count que ja estava salvo e preservado
    saved = repository.items[job.id]
    assert saved.recommendation_count == 5
    assert saved.status is UrlIngestionJobStatus.COMPLETED


@pytest.mark.anyio
async def test_analyzing_retry_after_briefing_failure_skips_recommendations() -> None:
    """Cenario real de DT-09: briefing falha, retry pula recommendations.

    1a entrega: recommendations OK (salvo com done=True), briefing falha -> job.fail()
    2a entrega: recommendations nao e re-executado; briefing e re-executado
    """
    scraping_result_id = uuid4()
    existing_startup_id = uuid4()
    repository = FakeUrlIngestionJobRepository()

    # Job no estado em que estaria apos 1a entrega com recommendations OK + briefing falhou:
    # o use case chama job.fail() -> status = FAILED, mas as guardas (startup_id,
    # evidence_attached, recommendations_done) ficam persistidas.
    # Para testar o retry, precisamos repor o status para ANALYZING manualmente
    # (o que o Dramatiq faria via redelivery nao existindo em testes unitarios).
    job = UrlIngestionJob(url="https://acme.example.com")
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=scraping_result_id, ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    job.link_startup(existing_startup_id)
    job.mark_evidence_attached()
    job.record_recommendations(3)
    # Briefing falhou — status ANALYZING ainda (nao foi fail() no estado salvo)
    await repository.save(job)

    recs_port = FakeRecommendationsPort(count=99)
    briefing_port = FakeBriefingPort()
    use_case = _make_advance_use_case(
        repository=repository,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme AI", clean_text="conteudo")
        ),
        startups_port=FakeStartupsPort(startup_id=existing_startup_id),
        recommendations_port=recs_port,
        briefing_port=briefing_port,
    )

    await use_case.execute(job_id=job.id)

    # recommendations nunca chamado
    assert recs_port.calls == []
    # briefing chamado uma vez
    assert len(briefing_port.calls) == 1
    assert repository.items[job.id].status is UrlIngestionJobStatus.COMPLETED


# ---------------------------------------------------------------------------
# P0d — extração de links reais do HTML da home
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_analyzing_uses_real_links_from_html_instead_of_fixed_paths() -> None:
    """P0d: quando há HTML da home, usa links reais extraídos em vez de ENRICHMENT_PATHS.

    O HTML contém /plataforma (link real que NÃO está em ENRICHMENT_PATHS).
    O job deve usar esse link como candidato de enriquecimento.
    """
    scraping_result_id = uuid4()
    repository = FakeUrlIngestionJobRepository()

    # Job já está em ANALYZING — o execute() entra diretamente nesse branch.
    job = UrlIngestionJob(url="https://acme.example.com")
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=scraping_result_id, ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    await repository.save(job)

    html_with_real_links = (
        '<a href="/plataforma">Nossa Plataforma</a>'
        '<a href="/sobre">Sobre nós</a>'
        '<a href="https://other.example.com/page">Externo</a>'
        '<a href="/login">Login</a>'  # deve ser ignorado
    )

    scraping_port = FakeScrapingPort(
        status=StepStatus(is_done=True, is_failed=False, result_id=scraping_result_id, error_message=None),
        html=html_with_real_links,
    )

    use_case = _make_advance_use_case(
        repository=repository,
        scraping_port=scraping_port,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme", clean_text="conteudo")
        ),
        startups_port=FakeStartupsPort(
            profile=StartupProfileSnapshot(
                name="Acme",
                website_url="https://acme.example.com",
                founders=[],        # sinal ausente → enriquecimento acionado
                funding_stage=None,  # sinal ausente
                customers=[],       # sinal ausente
                evidence_urls=[],
            )
        ),
    )

    # Uma única chamada: o job já está em ANALYZING e completa (com enriquecimento agendado).
    with pytest.raises(UrlIngestionStillProcessingError):
        await use_case.execute(job_id=job.id)

    enrichment_jobs = [
        j for j in repository.items.values()
        if j.id != job.id and j.enrichment_round == 1
    ]
    enrichment_urls = {j.url for j in enrichment_jobs}

    assert enrichment_urls, "Esperava ao menos 1 job de enriquecimento agendado"

    # /plataforma é um link REAL do HTML e não está em ENRICHMENT_PATHS — confirma
    # que foram usados os links extraídos, não os paths fixos.
    assert any("plataforma" in u for u in enrichment_urls), (
        f"Link real /plataforma deveria aparecer; obteve: {enrichment_urls}"
    )
    # /login é segmento bloqueado — não deve aparecer
    assert not any("login" in u for u in enrichment_urls), (
        f"Segmento /login não deveria ser candidato: {enrichment_urls}"
    )
    # Link externo (other.example.com) não deve aparecer
    assert not any("other.example.com" in u for u in enrichment_urls), (
        f"Link externo não deveria ser candidato: {enrichment_urls}"
    )


@pytest.mark.anyio
async def test_analyzing_falls_back_to_fixed_paths_when_html_is_none() -> None:
    """P0d: quando get_html retorna None, usa ENRICHMENT_PATHS como fallback."""
    scraping_result_id = uuid4()
    repository = FakeUrlIngestionJobRepository()

    # Job já está em ANALYZING — o execute() entra diretamente nesse branch.
    job = UrlIngestionJob(url="https://acme.example.com")
    job.start_scraping(uuid4())
    job.start_ingesting(scraping_result_id=scraping_result_id, ingestion_job_id=uuid4())
    job.start_embedding(document_id=uuid4(), embedding_job_id=uuid4())
    job.start_analyzing()
    await repository.save(job)

    scraping_port = FakeScrapingPort(
        status=StepStatus(is_done=True, is_failed=False, result_id=scraping_result_id, error_message=None),
        html=None,  # HTML indisponível → fallback para ENRICHMENT_PATHS
    )

    use_case = _make_advance_use_case(
        repository=repository,
        scraping_port=scraping_port,
        ingestion_port=FakeIngestionPort(
            content=DocumentContentView(title="Acme", clean_text="conteudo")
        ),
        startups_port=FakeStartupsPort(
            profile=StartupProfileSnapshot(
                name="Acme",
                website_url="https://acme.example.com",
                founders=[],        # sinal ausente → enriquecimento acionado
                funding_stage=None,  # sinal ausente
                customers=[],       # sinal ausente
                evidence_urls=[],
            )
        ),
    )

    # Uma única chamada: o job já está em ANALYZING e completa (com enriquecimento agendado).
    with pytest.raises(UrlIngestionStillProcessingError):
        await use_case.execute(job_id=job.id)

    enrichment_jobs = [
        j for j in repository.items.values()
        if j.id != job.id and j.enrichment_round == 1
    ]
    enrichment_urls = {j.url for j in enrichment_jobs}

    assert enrichment_urls, "Esperava ao menos 1 job de enriquecimento agendado"

    # Fallback: pelo menos 1 dos paths fixos de ENRICHMENT_PATHS deve aparecer.
    # /plataforma NÃO está em ENRICHMENT_PATHS, logo não pode aparecer aqui.
    assert any(
        "sobre" in u or "about" in u or "blog" in u
        for u in enrichment_urls
    ), f"Sem HTML, esperava paths fixos (sobre/about/blog); obteve: {enrichment_urls}"
    assert not any("plataforma" in u for u in enrichment_urls), (
        f"/plataforma só aparece via HTML extraction, não deve estar aqui: {enrichment_urls}"
    )
