"""Testes do registry de fontes NVIDIA Knowledge V2."""

import pytest

from apps.api.src.modules.nvidia_knowledge.application.dto import (
    ListNvidiaKnowledgeSourcesInput,
)
from apps.api.src.modules.nvidia_knowledge.application.use_cases.list_nvidia_knowledge_sources import (
    ListNvidiaKnowledgeSources,
)
from apps.api.src.modules.nvidia_knowledge.domain.enums import (
    NvidiaKnowledgeSourcePriority,
)
from apps.api.src.modules.nvidia_knowledge.infrastructure.static_catalog.static_source_repository import (
    StaticNvidiaKnowledgeSourceRepository,
)
from apps.api.src.modules.nvidia_knowledge.infrastructure.static_catalog.catalog_data import (
    INITIAL_NVIDIA_TECHNOLOGIES,
)


@pytest.mark.anyio
async def test_source_registry_lists_sources_sorted_by_priority() -> None:
    registry = ListNvidiaKnowledgeSources(StaticNvidiaKnowledgeSourceRepository())

    sources = await registry.list_sources(ListNvidiaKnowledgeSourcesInput())

    assert len(sources) >= 16
    assert [source.priority.value for source in sources] == sorted(
        source.priority.value for source in sources
    )
    assert all(source.url.startswith("https://") for source in sources)
    assert all(source.document_source_type == "nvidia_knowledge" for source in sources)


@pytest.mark.anyio
async def test_source_registry_filters_by_priority() -> None:
    registry = ListNvidiaKnowledgeSources(StaticNvidiaKnowledgeSourceRepository())

    sources = await registry.list_sources(
        ListNvidiaKnowledgeSourcesInput(priority=NvidiaKnowledgeSourcePriority.P0)
    )

    assert {source.technology_slug for source in sources} >= {
        "nvidia-inception",
        "nvidia-nim",
        "nvidia-nemo",
        "nemo-guardrails",
        "triton-inference-server",
        "tensorrt-llm",
        "nvidia-ai-enterprise",
    }
    assert all(source.priority == NvidiaKnowledgeSourcePriority.P0 for source in sources)


@pytest.mark.anyio
async def test_source_registry_filters_by_technology_slug_case_insensitive() -> None:
    registry = ListNvidiaKnowledgeSources(StaticNvidiaKnowledgeSourceRepository())

    sources = await registry.list_sources(
        ListNvidiaKnowledgeSourcesInput(technology_slug="NVIDIA-NIM")
    )

    assert sources
    assert {source.technology_slug for source in sources} == {"nvidia-nim"}


@pytest.mark.anyio
async def test_source_registry_searches_by_tags_and_description() -> None:
    registry = ListNvidiaKnowledgeSources(StaticNvidiaKnowledgeSourceRepository())

    voice_sources = await registry.list_sources(
        ListNvidiaKnowledgeSourcesInput(query="voice")
    )
    governance_sources = await registry.list_sources(
        ListNvidiaKnowledgeSourcesInput(query="governance")
    )

    assert any(source.technology_slug == "riva" for source in voice_sources)
    assert any(
        source.technology_slug == "nvidia-ai-enterprise"
        for source in governance_sources
    )


@pytest.mark.anyio
async def test_source_registry_covers_current_catalog_technologies() -> None:
    registry = ListNvidiaKnowledgeSources(StaticNvidiaKnowledgeSourceRepository())

    sources = await registry.list_sources(ListNvidiaKnowledgeSourcesInput())
    source_technology_slugs = {
        source.technology_slug
        for source in sources
        if source.technology_slug is not None
    }
    catalog_slugs = {technology.slug for technology in INITIAL_NVIDIA_TECHNOLOGIES}

    assert catalog_slugs <= source_technology_slugs
