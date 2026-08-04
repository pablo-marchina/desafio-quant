"""Schemas Pydantic do modulo NVIDIA Knowledge."""

from pydantic import BaseModel, Field

from apps.api.src.modules.nvidia_knowledge.application.dto import (
    NvidiaKnowledgeSourceView,
    NvidiaTechnologyView,
    SubmittedNvidiaKnowledgeSourceView,
    SubmitNvidiaKnowledgeSourcesView,
)
from apps.api.src.modules.nvidia_knowledge.domain.enums import (
    NvidiaKnowledgeSourcePriority,
    NvidiaKnowledgeSourceType,
    NvidiaTechnologyCategory,
)


class NvidiaTechnologyResponse(BaseModel):
    slug: str
    name: str
    category: NvidiaTechnologyCategory
    description: str
    use_cases: list[str]
    keywords: list[str]
    official_url: str
    complexity: str
    supported_workloads: dict[str, float]

    @classmethod
    def from_view(cls, view: NvidiaTechnologyView) -> "NvidiaTechnologyResponse":
        return cls(
            slug=view.slug,
            name=view.name,
            category=view.category,
            description=view.description,
            use_cases=view.use_cases,
            keywords=view.keywords,
            official_url=view.official_url,
            complexity=view.complexity,
            supported_workloads=view.supported_workloads,
        )


class NvidiaKnowledgeSourceResponse(BaseModel):
    slug: str
    title: str
    url: str
    source_type: NvidiaKnowledgeSourceType
    priority: NvidiaKnowledgeSourcePriority
    technology_slug: str | None
    description: str
    tags: list[str]
    document_source_type: str

    @classmethod
    def from_view(
        cls,
        view: NvidiaKnowledgeSourceView,
    ) -> "NvidiaKnowledgeSourceResponse":
        return cls(
            slug=view.slug,
            title=view.title,
            url=view.url,
            source_type=view.source_type,
            priority=view.priority,
            technology_slug=view.technology_slug,
            description=view.description,
            tags=view.tags,
            document_source_type=view.document_source_type,
        )


class SubmitNvidiaKnowledgeSourcesRequest(BaseModel):
    priority: NvidiaKnowledgeSourcePriority | None = None
    technology_slug: str | None = None
    query: str | None = None
    limit: int | None = Field(default=None, ge=1)


class SubmittedNvidiaKnowledgeSourceResponse(BaseModel):
    source_slug: str
    title: str
    url: str
    priority: NvidiaKnowledgeSourcePriority
    technology_slug: str | None
    url_ingestion_job_id: str

    @classmethod
    def from_view(
        cls,
        view: SubmittedNvidiaKnowledgeSourceView,
    ) -> "SubmittedNvidiaKnowledgeSourceResponse":
        return cls(
            source_slug=view.source_slug,
            title=view.title,
            url=view.url,
            priority=view.priority,
            technology_slug=view.technology_slug,
            url_ingestion_job_id=view.url_ingestion_job_id,
        )


class SubmitNvidiaKnowledgeSourcesResponse(BaseModel):
    total: int
    submitted: list[SubmittedNvidiaKnowledgeSourceResponse]

    @classmethod
    def from_view(
        cls,
        view: SubmitNvidiaKnowledgeSourcesView,
    ) -> "SubmitNvidiaKnowledgeSourcesResponse":
        return cls(
            total=view.total,
            submitted=[
                SubmittedNvidiaKnowledgeSourceResponse.from_view(item)
                for item in view.submitted
            ],
        )
