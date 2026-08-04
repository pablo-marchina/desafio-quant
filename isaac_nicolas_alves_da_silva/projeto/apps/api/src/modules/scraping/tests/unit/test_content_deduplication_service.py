"""Testes do servico que detecta resultados de scraping duplicados."""

from uuid import uuid4

import pytest

from apps.api.src.modules.scraping.application.content_deduplication_service import (
    ContentDeduplicationService,
)
from apps.api.src.modules.scraping.domain.entities import ScrapingResult
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.infrastructure.repositories.in_memory_result_repository import (
    InMemoryScrapingResultRepository,
)


def create_result(*, content_hash: str) -> ScrapingResult:
    """Cria um resultado minimo para manter os testes focados na duplicidade."""

    return ScrapingResult(
        job_id=uuid4(),
        url="https://example.com",
        final_url="https://example.com",
        title="Example",
        raw_html="<html>Example</html>",
        raw_text="Example",
        method=ScrapingMethod.BEAUTIFULSOUP,
        status_code=200,
        technical_score=1.0,
        text_score=1.0,
        evidence_score=1.0,
        quality_score=1.0,
        content_hash=content_hash,
    )


@pytest.mark.anyio
async def test_finds_result_with_same_content_hash() -> None:
    repository = InMemoryScrapingResultRepository()
    existing_result = create_result(content_hash="same-hash")
    await repository.save(existing_result)
    service = ContentDeduplicationService(repository)

    duplicate = await service.find_duplicate(create_result(content_hash="same-hash"))

    assert duplicate == existing_result


@pytest.mark.anyio
async def test_returns_none_for_new_content() -> None:
    repository = InMemoryScrapingResultRepository()
    service = ContentDeduplicationService(repository)

    duplicate = await service.find_duplicate(create_result(content_hash="new-hash"))

    assert duplicate is None


@pytest.mark.anyio
async def test_does_not_consider_same_result_a_duplicate() -> None:
    repository = InMemoryScrapingResultRepository()
    result = create_result(content_hash="same-hash")
    await repository.save(result)
    service = ContentDeduplicationService(repository)

    duplicate = await service.find_duplicate(result)

    assert duplicate is None
