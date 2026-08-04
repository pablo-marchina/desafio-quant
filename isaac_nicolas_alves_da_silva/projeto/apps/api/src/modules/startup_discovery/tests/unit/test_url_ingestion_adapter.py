"""Testes do adapter de submissao do discovery para url_ingestion."""

from datetime import datetime, timezone
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.orchestration.application.dto import (
    CreateUrlIngestionJobInput,
    UrlIngestionJobView,
)
from apps.api.src.modules.orchestration.domain.enums import UrlIngestionJobStatus
from apps.api.src.modules.startup_discovery.infrastructure.orchestration_adapters.url_ingestion_adapter import (
    StartupDiscoveryUrlIngestionAdapter,
)
from apps.api.src.modules.startups.domain.entities import Startup


class FakeCreateUrlIngestionJob:
    def __init__(self) -> None:
        self.received_input: CreateUrlIngestionJobInput | None = None

    async def execute(
        self, job_input: CreateUrlIngestionJobInput
    ) -> UrlIngestionJobView:
        self.received_input = job_input
        now = datetime.now(timezone.utc)
        return UrlIngestionJobView(
            id=uuid4(),
            url=job_input.url,
            source_type=job_input.source_type,
            status=UrlIngestionJobStatus.PENDING,
            startup_id=job_input.startup_id,
            parent_job_id=job_input.parent_job_id,
            enrichment_round=job_input.enrichment_round,
            scraping_job_id=None,
            scraping_result_id=None,
            ingestion_job_id=None,
            document_id=None,
            embedding_job_id=None,
            recommendation_count=None,
            briefing_id=None,
            error_message=None,
            created_at=now,
            started_at=None,
            finished_at=None,
        )


class FakeStartupRepository:
    def __init__(self, startups: list[Startup]) -> None:
        self._startups = startups

    async def list_all(self) -> list[Startup]:
        return self._startups


class FakeStartupsUoW:
    def __init__(self, startups: list[Startup]) -> None:
        self.startup_repository = FakeStartupRepository(startups)

    async def __aenter__(self) -> "FakeStartupsUoW":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        pass


@pytest.mark.anyio
async def test_discovery_adapter_reuses_existing_startup_by_normalized_domain() -> None:
    existing = Startup(
        id=uuid4(),
        name="NeuralMind",
        website_url="https://neuralmind.ai/",
    )
    use_case = FakeCreateUrlIngestionJob()
    adapter = StartupDiscoveryUrlIngestionAdapter(
        use_case, lambda: FakeStartupsUoW([existing])
    )

    await adapter.submit("https://www.neuralmind.ai/blog", name="NeuralMind")

    assert use_case.received_input is not None
    assert use_case.received_input.startup_id == existing.id


@pytest.mark.anyio
async def test_discovery_adapter_submits_without_startup_id_when_no_duplicate() -> None:
    use_case = FakeCreateUrlIngestionJob()
    adapter = StartupDiscoveryUrlIngestionAdapter(use_case, lambda: FakeStartupsUoW([]))

    await adapter.submit("https://new-startup.ai", name="New Startup")

    assert use_case.received_input is not None
    assert use_case.received_input.startup_id is None
