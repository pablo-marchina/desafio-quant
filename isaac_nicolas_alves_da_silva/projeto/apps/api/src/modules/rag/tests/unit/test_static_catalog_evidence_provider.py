"""Testes das evidencias suplementares do catalogo NVIDIA."""

import pytest

from apps.api.src.modules.rag.infrastructure.nvidia_knowledge_adapters.static_catalog_evidence_provider import (
    StaticNvidiaKnowledgeEvidenceProvider,
)


@pytest.mark.anyio
async def test_provider_returns_matching_nvidia_technology_evidence() -> None:
    provider = StaticNvidiaKnowledgeEvidenceProvider()

    results = await provider.find(
        "What does NVIDIA Clara provide for healthcare and life sciences?",
        source_type="nvidia_knowledge",
        limit=3,
    )

    assert results
    assert results[0].source_type == "nvidia_knowledge"
    assert results[0].source_url == "https://www.nvidia.com/en-us/clara/"
    assert "healthcare" in results[0].text.lower()
    assert "life sciences" in results[0].text.lower()


@pytest.mark.anyio
async def test_provider_ignores_non_nvidia_knowledge_source_type() -> None:
    provider = StaticNvidiaKnowledgeEvidenceProvider()

    results = await provider.find(
        "What does NVIDIA Clara provide?",
        source_type="startup_evidence",
        limit=3,
    )

    assert results == []
