"""Testes da submissao de fontes NVIDIA Knowledge para scraping."""

from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.nvidia_knowledge.application.dto import (
    ListNvidiaKnowledgeSourcesInput,
    NvidiaKnowledgeSourceView,
    SubmitNvidiaKnowledgeSourcesInput,
)
from apps.api.src.modules.nvidia_knowledge.application.ports import (
    NvidiaKnowledgeUrlIngestionSubmitter,
)
from apps.api.src.modules.nvidia_knowledge.application.public.source_registry import (
    NvidiaKnowledgeSourceRegistry,
)
from apps.api.src.modules.nvidia_knowledge.application.use_cases.submit_nvidia_knowledge_sources import (
    SubmitNvidiaKnowledgeSources,
)
from apps.api.src.modules.nvidia_knowledge.domain.enums import (
    NvidiaKnowledgeSourcePriority,
    NvidiaKnowledgeSourceType,
)


class FakeSourceRegistry(NvidiaKnowledgeSourceRegistry):
    def __init__(self, sources: list[NvidiaKnowledgeSourceView]) -> None:
        self.sources = sources
        self.received_input: ListNvidiaKnowledgeSourcesInput | None = None

    async def list_sources(
        self,
        registry_input: ListNvidiaKnowledgeSourcesInput,
    ) -> list[NvidiaKnowledgeSourceView]:
        self.received_input = registry_input
        return self.sources


class FakeUrlIngestionSubmitter(NvidiaKnowledgeUrlIngestionSubmitter):
    def __init__(self) -> None:
        self.submitted_urls: list[str] = []
        self.submitted_source_types: list[str] = []
        self.job_ids: list[UUID] = [uuid4(), uuid4(), uuid4()]

    async def submit(
        self,
        url: str,
        *,
        source_type: str,
    ) -> UUID:
        self.submitted_urls.append(url)
        self.submitted_source_types.append(source_type)
        return self.job_ids[len(self.submitted_urls) - 1]


def make_source(
    slug: str,
    url: str,
    priority: NvidiaKnowledgeSourcePriority = NvidiaKnowledgeSourcePriority.P0,
    technology_slug: str | None = "nvidia-nim",
) -> NvidiaKnowledgeSourceView:
    return NvidiaKnowledgeSourceView(
        slug=slug,
        title=slug.replace("-", " ").title(),
        url=url,
        source_type=NvidiaKnowledgeSourceType.OFFICIAL_DOCS,
        priority=priority,
        technology_slug=technology_slug,
        description="Official NVIDIA docs.",
        tags=["nvidia", "docs"],
    )


@pytest.mark.anyio
async def test_submit_nvidia_sources_creates_scraping_jobs_for_registry_sources() -> None:
    registry = FakeSourceRegistry(
        [
            make_source("nvidia-nim-docs", "https://docs.nvidia.com/nim/"),
            make_source("nvidia-nemo-docs", "https://docs.nvidia.com/nemo/"),
        ]
    )
    url_ingestion_submitter = FakeUrlIngestionSubmitter()
    use_case = SubmitNvidiaKnowledgeSources(
        source_registry=registry,
        url_ingestion_submitter=url_ingestion_submitter,
    )

    result = await use_case.execute(SubmitNvidiaKnowledgeSourcesInput())

    assert result.total == 2
    assert url_ingestion_submitter.submitted_urls == [
        "https://docs.nvidia.com/nim/",
        "https://docs.nvidia.com/nemo/",
    ]
    assert url_ingestion_submitter.submitted_source_types == [
        "nvidia_knowledge",
        "nvidia_knowledge",
    ]
    assert [item.url_ingestion_job_id for item in result.submitted] == [
        str(url_ingestion_submitter.job_ids[0]),
        str(url_ingestion_submitter.job_ids[1]),
    ]


@pytest.mark.anyio
async def test_submit_nvidia_sources_forwards_filters_and_honors_limit() -> None:
    registry = FakeSourceRegistry(
        [
            make_source("source-a", "https://example.com/a"),
            make_source("source-b", "https://example.com/b"),
            make_source("source-c", "https://example.com/c"),
        ]
    )
    url_ingestion_submitter = FakeUrlIngestionSubmitter()
    use_case = SubmitNvidiaKnowledgeSources(
        source_registry=registry,
        url_ingestion_submitter=url_ingestion_submitter,
    )

    result = await use_case.execute(
        SubmitNvidiaKnowledgeSourcesInput(
            priority=NvidiaKnowledgeSourcePriority.P0,
            technology_slug="nvidia-nim",
            query="inference",
            limit=2,
        )
    )

    assert registry.received_input == ListNvidiaKnowledgeSourcesInput(
        priority=NvidiaKnowledgeSourcePriority.P0,
        technology_slug="nvidia-nim",
        query="inference",
    )
    assert result.total == 2
    assert url_ingestion_submitter.submitted_urls == [
        "https://example.com/a",
        "https://example.com/b",
    ]
