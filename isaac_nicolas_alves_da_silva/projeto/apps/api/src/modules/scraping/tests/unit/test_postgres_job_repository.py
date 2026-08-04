"""Testes unitários do repositório PostgreSQL de jobs."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from apps.api.src.modules.scraping.domain.entities import ScrapingJob
from apps.api.src.modules.scraping.domain.enums import JobStatus
from apps.api.src.modules.scraping.infrastructure.database.mappers.scraping_job_mapper import (
    ScrapingJobMapper,
)
from apps.api.src.modules.scraping.infrastructure.database.repositories.postgres_job_repository import (
    PostgresScrapingJobRepository,
)


@pytest.mark.anyio
async def test_save_adds_new_job_model_and_flushes() -> None:
    """Job inexistente deve gerar um novo model na sessão."""

    session = Mock()
    session.get = AsyncMock(return_value=None)
    session.flush = AsyncMock()
    session.add = Mock()
    repository = PostgresScrapingJobRepository(session)
    job = ScrapingJob(url="https://example.com")

    await repository.save(job)

    added_model = session.add.call_args.args[0]
    assert added_model.id == job.id
    assert added_model.status == JobStatus.PENDING.value
    session.flush.assert_awaited_once()


@pytest.mark.anyio
async def test_save_updates_existing_job_model() -> None:
    """Job existente deve ser atualizado sem adicionar outro registro."""

    job = ScrapingJob(url="https://example.com")
    existing_model = ScrapingJobMapper.to_model(job)
    session = Mock()
    session.get = AsyncMock(return_value=existing_model)
    session.flush = AsyncMock()
    session.add = Mock()
    repository = PostgresScrapingJobRepository(session)

    job.start()
    await repository.save(job)

    assert existing_model.status == JobStatus.RUNNING.value
    session.add.assert_not_called()
    session.flush.assert_awaited_once()


@pytest.mark.anyio
async def test_get_by_id_restores_result_id() -> None:
    """O result_id deve ser consultado na tabela de resultados."""

    job = ScrapingJob(url="https://example.com")
    result_id = uuid4()
    session = Mock()
    session.get = AsyncMock(return_value=ScrapingJobMapper.to_model(job))
    session.scalar = AsyncMock(return_value=result_id)
    repository = PostgresScrapingJobRepository(session)

    restored = await repository.get_by_id(job.id)

    assert restored is not None
    assert restored.id == job.id
    assert restored.result_id == result_id


@pytest.mark.anyio
async def test_get_by_id_restores_cached_completed_result_id_by_url() -> None:
    """Jobs completados por cache usam resultado recente de outro job."""

    job = ScrapingJob(url="https://example.com")
    job.start()
    job.complete(uuid4())
    result_id = uuid4()
    session = Mock()
    session.get = AsyncMock(return_value=ScrapingJobMapper.to_model(job))
    session.scalar = AsyncMock(side_effect=[None, result_id])
    repository = PostgresScrapingJobRepository(session)

    restored = await repository.get_by_id(job.id)

    assert restored is not None
    assert restored.id == job.id
    assert restored.result_id == result_id
    assert session.scalar.await_count == 2


@pytest.mark.anyio
async def test_get_by_id_returns_none_for_missing_job() -> None:
    """Consulta inexistente não deve tentar procurar resultado."""

    session = Mock()
    session.get = AsyncMock(return_value=None)
    session.scalar = AsyncMock()
    repository = PostgresScrapingJobRepository(session)

    restored = await repository.get_by_id(uuid4())

    assert restored is None
    session.scalar.assert_not_awaited()
