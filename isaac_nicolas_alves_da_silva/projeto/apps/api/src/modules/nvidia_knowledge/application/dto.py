"""DTOs do modulo NVIDIA Knowledge."""

from dataclasses import dataclass

from apps.api.src.modules.nvidia_knowledge.domain.enums import (
    NvidiaKnowledgeSourcePriority,
    NvidiaKnowledgeSourceType,
    NvidiaTechnologyCategory,
)


@dataclass(frozen=True)
class ListNvidiaTechnologiesInput:
    category: NvidiaTechnologyCategory | None = None
    query: str | None = None


@dataclass(frozen=True)
class NvidiaTechnologyView:
    slug: str
    name: str
    category: NvidiaTechnologyCategory
    description: str
    use_cases: list[str]
    keywords: list[str]
    official_url: str
    complexity: str
    supported_workloads: dict[str, float]


@dataclass(frozen=True)
class ListNvidiaKnowledgeSourcesInput:
    priority: NvidiaKnowledgeSourcePriority | None = None
    technology_slug: str | None = None
    query: str | None = None


@dataclass(frozen=True)
class SubmitNvidiaKnowledgeSourcesInput:
    priority: NvidiaKnowledgeSourcePriority | None = None
    technology_slug: str | None = None
    query: str | None = None
    limit: int | None = None


@dataclass(frozen=True)
class NvidiaKnowledgeSourceView:
    slug: str
    title: str
    url: str
    source_type: NvidiaKnowledgeSourceType
    priority: NvidiaKnowledgeSourcePriority
    technology_slug: str | None
    description: str
    tags: list[str]
    document_source_type: str = "nvidia_knowledge"


@dataclass(frozen=True)
class SubmittedNvidiaKnowledgeSourceView:
    source_slug: str
    title: str
    url: str
    priority: NvidiaKnowledgeSourcePriority
    technology_slug: str | None
    url_ingestion_job_id: str


@dataclass(frozen=True)
class SubmitNvidiaKnowledgeSourcesView:
    total: int
    submitted: list[SubmittedNvidiaKnowledgeSourceView]
