"""Testes unitários do repositório PostgreSQL de resultados."""

from hashlib import sha256
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest

from apps.api.src.modules.scraping.domain.entities import ScrapingResult
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.infrastructure.database.mappers.scraping_result_mapper import (
    ScrapingResultMapper,
)
from apps.api.src.modules.scraping.infrastructure.database.repositories.postgres_result_repository import (
    PostgresScrapingResultRepository,
)


def make_result() -> ScrapingResult:
    """Cria um resultado completo reutilizado pelos testes."""

    text = "Conteúdo aprovado."
    return ScrapingResult(
        job_id=uuid4(),
        url="https://example.com",
        final_url="https://example.com",
        title="Startup",
        raw_html=f"<html>{text}</html>",
        raw_text=text,
        method=ScrapingMethod.BEAUTIFULSOUP,
        status_code=200,
        technical_score=1.0,
        text_score=0.90,
        evidence_score=0.80,
        quality_score=0.89,
        content_hash=sha256(text.encode("utf-8")).hexdigest(),
        metadata={"response_bytes": 100},
    )


@pytest.mark.anyio
async def test_save_adds_new_result_and_flushes() -> None:
    """Resultado inexistente deve gerar novo model."""

    session = MagicMock()
    session.get = AsyncMock(return_value=None)
    session.add = Mock()
    session.flush = AsyncMock()
    repository = PostgresScrapingResultRepository(session)
    result = make_result()

    await repository.save(result)

    added_model = session.add.call_args.args[0]
    assert added_model.id == result.id
    assert added_model.content_hash == result.content_hash
    session.flush.assert_awaited_once()


@pytest.mark.anyio
async def test_save_updates_existing_result() -> None:
    """Resultado existente deve ser atualizado sem novo insert."""

    result = make_result()
    existing_model = ScrapingResultMapper.to_model(result)
    session = MagicMock()
    session.get = AsyncMock(return_value=existing_model)
    session.add = Mock()
    session.flush = AsyncMock()
    repository = PostgresScrapingResultRepository(session)

    result.title = "Título atualizado"
    await repository.save(result)

    assert existing_model.title == "Título atualizado"
    session.add.assert_not_called()


@pytest.mark.anyio
async def test_get_by_id_maps_existing_result() -> None:
    """Consulta por ID deve reconstruir a entidade."""

    result = make_result()
    session = Mock()
    session.get = AsyncMock(return_value=ScrapingResultMapper.to_model(result))
    repository = PostgresScrapingResultRepository(session)

    restored = await repository.get_by_id(result.id)

    assert restored is not None
    assert restored.id == result.id
    assert restored.metadata == result.metadata


@pytest.mark.anyio
async def test_get_by_content_hash_maps_existing_result() -> None:
    """Consulta por hash deve reconstruir o resultado encontrado."""

    result = make_result()
    session = Mock()
    session.scalar = AsyncMock(return_value=ScrapingResultMapper.to_model(result))
    repository = PostgresScrapingResultRepository(session)

    restored = await repository.get_by_content_hash(result.content_hash)

    assert restored is not None
    assert restored.content_hash == result.content_hash


@pytest.mark.anyio
async def test_queries_return_none_when_result_does_not_exist() -> None:
    """Ausência no banco deve ser representada por None."""

    session = Mock()
    session.get = AsyncMock(return_value=None)
    session.scalar = AsyncMock(return_value=None)
    repository = PostgresScrapingResultRepository(session)

    assert await repository.get_by_id(uuid4()) is None
    assert await repository.get_by_content_hash("missing") is None
