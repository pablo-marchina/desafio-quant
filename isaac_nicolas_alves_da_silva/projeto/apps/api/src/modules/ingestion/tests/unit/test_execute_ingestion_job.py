"""Testes do caso de uso ExecuteIngestionJob."""

from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.ingestion.application.dto import ScrapingResultData
from apps.api.src.modules.ingestion.application.ports import ScrapingResultReader
from apps.api.src.modules.ingestion.application.text_cleaner import TextCleaner
from apps.api.src.modules.ingestion.application.text_chunker import TextChunker
from apps.api.src.modules.ingestion.application.unit_of_work import IngestionUnitOfWork
from apps.api.src.modules.ingestion.application.use_cases.execute_ingestion_job import (
    ExecuteIngestionJob,
)
from apps.api.src.modules.ingestion.domain.entities import (
    Chunk,
    Document,
    IngestionJob,
    document_content_hash,
)
from apps.api.src.modules.ingestion.domain.enums import (
    DocumentSourceType,
    IngestionJobStatus,
)
from apps.api.src.modules.ingestion.domain.exceptions import IngestionJobNotFoundError
from apps.api.src.modules.ingestion.domain.repositories import (
    ChunkRepository,
    DocumentRepository,
    IngestionJobRepository,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeJobRepo(IngestionJobRepository):
    def __init__(self, job: IngestionJob | None = None) -> None:
        self._jobs: dict[UUID, IngestionJob] = {}
        if job:
            self._jobs[job.id] = job

    async def save(self, job: IngestionJob) -> None:
        self._jobs[job.id] = job

    async def get_by_id(self, job_id: UUID) -> IngestionJob | None:
        return self._jobs.get(job_id)

    async def get_by_scraping_result_id(self, scraping_result_id: UUID) -> IngestionJob | None:
        for j in self._jobs.values():
            if j.scraping_result_id == scraping_result_id:
                return j
        return None


class FakeDocRepo(DocumentRepository):
    def __init__(self) -> None:
        self.saved: list[Document] = []

    async def save(self, document: Document) -> None:
        self.saved.append(document)

    async def get_by_id(self, document_id: UUID) -> Document | None:
        return next((d for d in self.saved if d.id == document_id), None)

    async def find_by_content_hash(self, content_hash: str) -> Document | None:
        return next((d for d in self.saved if d.content_hash == content_hash), None)


class FakeChunkRepo(ChunkRepository):
    def __init__(self) -> None:
        self.saved: list[Chunk] = []

    async def save(self, chunk: Chunk) -> None:
        self.saved.append(chunk)

    async def list_by_document_id(self, document_id: UUID) -> list[Chunk]:
        return [c for c in self.saved if c.document_id == document_id]


class FakeUoW(IngestionUnitOfWork):
    def __init__(
        self,
        job_repo: FakeJobRepo,
        doc_repo: FakeDocRepo,
        chunk_repo: FakeChunkRepo,
    ) -> None:
        self.job_repository = job_repo
        self.document_repository = doc_repo
        self.chunk_repository = chunk_repo
        self.committed = False

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
        self.committed = True

    async def rollback(self) -> None:
        pass


class FakeScrapingResultReader(ScrapingResultReader):
    def __init__(self, data: ScrapingResultData | None) -> None:
        self._data = data

    async def get_by_id(self, result_id: UUID) -> ScrapingResultData | None:
        return self._data


def _make_result_data(raw_text: str = "texto de teste") -> ScrapingResultData:
    return ScrapingResultData(
        id=uuid4(),
        job_id=uuid4(),
        url="https://example.com",
        final_url="https://example.com",
        title="Titulo",
        raw_text=raw_text,
        quality_score=0.8,
        created_at=datetime.now(UTC),
    )


def _make_use_case(
    job: IngestionJob | None = None,
    result_data: ScrapingResultData | None = None,
    chunk_size: int = 2000,
) -> tuple[ExecuteIngestionJob, FakeJobRepo, FakeDocRepo, FakeChunkRepo]:
    job_repo = FakeJobRepo(job)
    doc_repo = FakeDocRepo()
    chunk_repo = FakeChunkRepo()
    uow = FakeUoW(job_repo, doc_repo, chunk_repo)

    use_case = ExecuteIngestionJob(
        uow_factory=lambda: uow,
        scraping_result_reader=FakeScrapingResultReader(result_data),
        text_cleaner=TextCleaner(),
        text_chunker=TextChunker(chunk_size=chunk_size, chunk_overlap=10),
    )
    return use_case, job_repo, doc_repo, chunk_repo


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_execute_starts_job() -> None:
    job = IngestionJob(scraping_result_id=uuid4())
    result_data = _make_result_data()
    use_case, job_repo, *_ = _make_use_case(job=job, result_data=result_data)

    await use_case.execute(job_id=job.id)

    saved = await job_repo.get_by_id(job.id)
    assert saved.status is IngestionJobStatus.COMPLETED
    assert saved.started_at is not None


@pytest.mark.anyio
async def test_execute_creates_document() -> None:
    job = IngestionJob(scraping_result_id=uuid4())
    result_data = _make_result_data("Texto limpo e simples.")
    use_case, job_repo, doc_repo, _ = _make_use_case(job=job, result_data=result_data)

    await use_case.execute(job_id=job.id)

    assert len(doc_repo.saved) == 1
    doc = doc_repo.saved[0]
    assert doc.url == "https://example.com"
    assert doc.ingestion_job_id == job.id
    assert doc.source_type is DocumentSourceType.STARTUP_EVIDENCE


@pytest.mark.anyio
async def test_execute_propagates_source_type_to_document() -> None:
    job = IngestionJob(
        scraping_result_id=uuid4(),
        source_type=DocumentSourceType.NVIDIA_KNOWLEDGE,
    )
    result_data = _make_result_data("Documentacao oficial NVIDIA NIM.")
    use_case, _, doc_repo, _ = _make_use_case(job=job, result_data=result_data)

    await use_case.execute(job_id=job.id)

    assert doc_repo.saved[0].source_type is DocumentSourceType.NVIDIA_KNOWLEDGE


@pytest.mark.anyio
async def test_execute_creates_chunks() -> None:
    long_text = "palavra " * 200  # ~1600 chars
    job = IngestionJob(scraping_result_id=uuid4())
    result_data = _make_result_data(long_text)
    use_case, _, doc_repo, chunk_repo = _make_use_case(
        job=job, result_data=result_data, chunk_size=200
    )

    await use_case.execute(job_id=job.id)

    assert len(chunk_repo.saved) > 1
    for i, chunk in enumerate(chunk_repo.saved):
        assert chunk.chunk_index == i


@pytest.mark.anyio
async def test_execute_completes_job_with_document_id() -> None:
    job = IngestionJob(scraping_result_id=uuid4())
    result_data = _make_result_data()
    use_case, job_repo, doc_repo, _ = _make_use_case(job=job, result_data=result_data)

    await use_case.execute(job_id=job.id)

    saved_job = await job_repo.get_by_id(job.id)
    assert saved_job.status is IngestionJobStatus.COMPLETED
    assert saved_job.document_id == doc_repo.saved[0].id


@pytest.mark.anyio
async def test_execute_fails_job_when_result_not_found() -> None:
    job = IngestionJob(scraping_result_id=uuid4())
    use_case, job_repo, *_ = _make_use_case(job=job, result_data=None)

    await use_case.execute(job_id=job.id)

    saved = await job_repo.get_by_id(job.id)
    assert saved.status is IngestionJobStatus.FAILED
    assert "IngestionSourceNotFoundError" in saved.error_message


@pytest.mark.anyio
async def test_execute_raises_when_job_not_found() -> None:
    use_case, *_ = _make_use_case(job=None, result_data=None)

    with pytest.raises(IngestionJobNotFoundError):
        await use_case.execute(job_id=uuid4())


@pytest.mark.anyio
async def test_execute_chunk_count_matches_document() -> None:
    long_text = "frase. " * 100
    job = IngestionJob(scraping_result_id=uuid4())
    result_data = _make_result_data(long_text)
    use_case, _, doc_repo, chunk_repo = _make_use_case(
        job=job, result_data=result_data, chunk_size=150
    )

    await use_case.execute(job_id=job.id)

    doc = doc_repo.saved[0]
    assert doc.chunk_count == len(chunk_repo.saved)


@pytest.mark.anyio
async def test_execute_cleans_text_before_chunking() -> None:
    dirty = "linha1\r\n\r\nlinha2\r\nlinha3"
    job = IngestionJob(scraping_result_id=uuid4())
    result_data = _make_result_data(dirty)
    use_case, _, doc_repo, _ = _make_use_case(job=job, result_data=result_data)

    await use_case.execute(job_id=job.id)

    doc = doc_repo.saved[0]
    assert "\r" not in doc.clean_text


@pytest.mark.anyio
async def test_execute_document_has_content_hash() -> None:
    job = IngestionJob(scraping_result_id=uuid4())
    result_data = _make_result_data("Texto qualquer para hash.")
    use_case, _, doc_repo, _ = _make_use_case(job=job, result_data=result_data)

    await use_case.execute(job_id=job.id)

    doc = doc_repo.saved[0]
    assert len(doc.content_hash) == 64  # SHA-256 hex


@pytest.mark.anyio
async def test_execute_reuses_existing_document_on_duplicate_content() -> None:
    """Re-scrape com conteudo identico nao cria Document nem Chunk novos."""

    # Simula um Document ja salvo com o mesmo hash do texto que vamos processar
    raw_text = "Texto de exemplo para dedup."
    clean = TextCleaner().clean(raw_text)
    existing_hash = document_content_hash(clean)

    job_first = IngestionJob(scraping_result_id=uuid4())
    existing_doc = Document(
        ingestion_job_id=job_first.id,
        scraping_result_id=job_first.scraping_result_id,
        url="https://startup.example.com",
        title="Startup",
        clean_text=clean,
        word_count=5,
        chunk_count=1,
        content_hash=existing_hash,
    )

    # Segundo job com o mesmo conteudo
    job_second = IngestionJob(scraping_result_id=uuid4())
    result_data = _make_result_data(raw_text)
    job_repo = FakeJobRepo(job_second)
    doc_repo = FakeDocRepo()
    await doc_repo.save(existing_doc)  # pre-popula o repo com o doc existente
    chunk_repo = FakeChunkRepo()
    uow = FakeUoW(job_repo, doc_repo, chunk_repo)

    use_case = ExecuteIngestionJob(
        uow_factory=lambda: uow,
        scraping_result_reader=FakeScrapingResultReader(result_data),
        text_cleaner=TextCleaner(),
        text_chunker=TextChunker(chunk_size=2000, chunk_overlap=10),
    )

    await use_case.execute(job_id=job_second.id)

    # Nao criou Document novo — so o pre-existente
    assert len(doc_repo.saved) == 1
    # Nao criou chunks novos
    assert len(chunk_repo.saved) == 0
    # Job concluido com o id do documento pre-existente
    saved_job = await job_repo.get_by_id(job_second.id)
    assert saved_job.status is IngestionJobStatus.COMPLETED
    assert saved_job.document_id == existing_doc.id
