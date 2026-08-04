"""Testes unitários do repositório PostgreSQL de tentativas."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from apps.api.src.modules.scraping.domain.entities import ScrapingAttempt
from apps.api.src.modules.scraping.domain.enums import (
    AttemptStatus,
    ScrapingMethod,
    ValidationDecision,
)
from apps.api.src.modules.scraping.infrastructure.database.mappers.scraping_attempt_mapper import (
    ScrapingAttemptMapper,
)
from apps.api.src.modules.scraping.infrastructure.database.repositories.postgres_attempt_repository import (
    PostgresScrapingAttemptRepository,
)


@pytest.mark.anyio
async def test_save_adds_new_attempt_and_flushes() -> None:
    """Tentativa inexistente deve gerar novo model na sessão."""

    session = Mock()
    session.get = AsyncMock(return_value=None)
    session.add = Mock()
    session.flush = AsyncMock()
    repository = PostgresScrapingAttemptRepository(session)
    attempt = ScrapingAttempt(
        job_id=uuid4(),
        method=ScrapingMethod.BEAUTIFULSOUP,
    )

    await repository.save(attempt)

    added_model = session.add.call_args.args[0]
    assert added_model.id == attempt.id
    assert added_model.status == AttemptStatus.RUNNING.value
    session.flush.assert_awaited_once()


@pytest.mark.anyio
async def test_save_updates_existing_attempt() -> None:
    """Finalização deve atualizar o model já persistido."""

    attempt = ScrapingAttempt(
        job_id=uuid4(),
        method=ScrapingMethod.BEAUTIFULSOUP,
    )
    existing_model = ScrapingAttemptMapper.to_model(attempt)
    session = Mock()
    session.get = AsyncMock(return_value=existing_model)
    session.add = Mock()
    session.flush = AsyncMock()
    repository = PostgresScrapingAttemptRepository(session)

    attempt.finish_validation(
        decision=ValidationDecision.ACCEPT,
        technical_score=1.0,
        text_score=0.90,
        evidence_score=0.80,
        quality_score=0.89,
        problems=[],
        warnings=[],
    )
    await repository.save(attempt)

    assert existing_model.status == AttemptStatus.ACCEPTED.value
    assert existing_model.quality_score == 0.89
    session.add.assert_not_called()


@pytest.mark.anyio
async def test_list_by_job_id_maps_query_results() -> None:
    """Consulta deve reconstruir entidades na ordem retornada pelo banco."""

    job_id = uuid4()
    first = ScrapingAttemptMapper.to_model(
        ScrapingAttempt(job_id, ScrapingMethod.BEAUTIFULSOUP)
    )
    second = ScrapingAttemptMapper.to_model(
        ScrapingAttempt(job_id, ScrapingMethod.PLAYWRIGHT)
    )
    scalar_result = Mock()
    scalar_result.all.return_value = [first, second]
    session = Mock()
    session.scalars = AsyncMock(return_value=scalar_result)
    repository = PostgresScrapingAttemptRepository(session)

    attempts = await repository.list_by_job_id(job_id)

    assert [attempt.method for attempt in attempts] == [
        ScrapingMethod.BEAUTIFULSOUP,
        ScrapingMethod.PLAYWRIGHT,
    ]
    session.scalars.assert_awaited_once()
