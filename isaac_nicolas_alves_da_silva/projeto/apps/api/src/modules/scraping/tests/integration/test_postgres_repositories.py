"""Testes integrados dos repositórios contra o PostgreSQL Docker."""

from datetime import timedelta
from hashlib import sha256

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.database.relational.session import engine
from apps.api.src.modules.scraping.domain.entities import (
    ScrapingAttempt,
    ScrapingJob,
    ScrapingResult,
    utc_now,
)
from apps.api.src.modules.scraping.domain.enums import (
    AttemptStatus,
    JobStatus,
    ScrapingMethod,
    ValidationDecision,
)
from apps.api.src.modules.scraping.domain.exceptions import (
    DuplicateScrapingContentError,
)
from apps.api.src.modules.scraping.infrastructure.database.repositories.postgres_attempt_repository import (
    PostgresScrapingAttemptRepository,
)
from apps.api.src.modules.scraping.infrastructure.database.repositories.postgres_job_repository import (
    PostgresScrapingJobRepository,
)
from apps.api.src.modules.scraping.infrastructure.database.repositories.postgres_result_repository import (
    PostgresScrapingResultRepository,
)


@pytest.mark.anyio
async def test_postgres_repositories_persist_and_restore_complete_flow() -> None:
    """Os três repositórios devem colaborar dentro da mesma transação."""

    # A conexão e a transação externas permitem fazer rollback no final. Assim,
    # o teste usa o PostgreSQL real sem deixar registros permanentes.
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
        )

        try:
            jobs = PostgresScrapingJobRepository(session)
            attempts = PostgresScrapingAttemptRepository(session)
            results = PostgresScrapingResultRepository(session)

            job = ScrapingJob(url="https://integration-test.example")
            await jobs.save(job)

            job.start()
            await jobs.save(job)

            attempt = ScrapingAttempt(
                job_id=job.id,
                method=ScrapingMethod.BEAUTIFULSOUP,
            )
            await attempts.save(attempt)
            attempt.finish_validation(
                decision=ValidationDecision.ACCEPT,
                technical_score=1.0,
                text_score=0.90,
                evidence_score=0.80,
                quality_score=0.89,
                problems=[],
                warnings=["integration_test"],
                semantic_confidence=0.86,
                agent_reviewed=True,
                agent_reason="Agente confirmou a evidencia.",
            )
            await attempts.save(attempt)

            raw_text = "Conteúdo aprovado pelo teste integrado."
            scraping_result = ScrapingResult(
                job_id=job.id,
                url=job.url,
                final_url=job.url,
                title="Teste integrado",
                raw_html=f"<html>{raw_text}</html>",
                raw_text=raw_text,
                method=ScrapingMethod.BEAUTIFULSOUP,
                status_code=200,
                technical_score=1.0,
                text_score=0.90,
                evidence_score=0.80,
                quality_score=0.89,
                content_hash=sha256(raw_text.encode("utf-8")).hexdigest(),
                metadata={"test": True},
            )
            await results.save(scraping_result)

            job.complete(scraping_result.id)
            await jobs.save(job)

            restored_job = await jobs.get_by_id(job.id)
            restored_attempts = await attempts.list_by_job_id(job.id)
            restored_result = await results.get_by_id(scraping_result.id)
            restored_by_hash = await results.get_by_content_hash(
                scraping_result.content_hash
            )

            assert restored_job is not None
            assert restored_job.status is JobStatus.COMPLETED
            assert restored_job.result_id == scraping_result.id

            assert len(restored_attempts) == 1
            assert restored_attempts[0].status is AttemptStatus.ACCEPTED
            assert restored_attempts[0].warnings == ["integration_test"]
            assert restored_attempts[0].semantic_confidence == 0.86
            assert restored_attempts[0].agent_reviewed is True
            assert restored_attempts[0].agent_reason == "Agente confirmou a evidencia."

            assert restored_result is not None
            assert restored_result.metadata == {"test": True}
            assert restored_by_hash is not None
            assert restored_by_hash.id == scraping_result.id
        finally:
            await session.close()
            await transaction.rollback()

    # O AnyIO cria loops independentes para testes distintos. Encerramos o
    # pool ainda no loop atual para nao reutilizar conexoes associadas a ele.
    await engine.dispose()


@pytest.mark.anyio
async def test_postgres_rejects_duplicate_content_hash() -> None:
    """O indice unico deve impedir dois resultados com o mesmo conteudo."""

    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)

        try:
            jobs = PostgresScrapingJobRepository(session)
            results = PostgresScrapingResultRepository(session)
            first_job = ScrapingJob(url="https://first.example")
            second_job = ScrapingJob(url="https://second.example")
            await jobs.save(first_job)
            await jobs.save(second_job)

            shared_hash = sha256(b"same content").hexdigest()

            def create_result(job: ScrapingJob) -> ScrapingResult:
                return ScrapingResult(
                    job_id=job.id,
                    url=job.url,
                    final_url=job.url,
                    title="Duplicate test",
                    raw_html="<html>same content</html>",
                    raw_text="same content",
                    method=ScrapingMethod.BEAUTIFULSOUP,
                    status_code=200,
                    technical_score=1.0,
                    text_score=1.0,
                    evidence_score=1.0,
                    quality_score=1.0,
                    content_hash=shared_hash,
                )

            first_result = create_result(first_job)
            await results.save(first_result)

            with pytest.raises(DuplicateScrapingContentError):
                await results.save(create_result(second_job))

            # O savepoint preserva a transacao externa depois da colisao.
            restored = await results.get_by_id(first_result.id)
            assert restored is not None
        finally:
            await session.close()
            await transaction.rollback()

    await engine.dispose()


@pytest.mark.anyio
async def test_get_recent_by_url_respects_time_window() -> None:
    """Cache de scraping: so reaproveita resultado dentro da janela informada."""

    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)

        try:
            jobs = PostgresScrapingJobRepository(session)
            results = PostgresScrapingResultRepository(session)
            job = ScrapingJob(url="https://cache-test.example")
            await jobs.save(job)

            scraping_result = ScrapingResult(
                job_id=job.id,
                url=job.url,
                final_url=job.url,
                title="Cache test",
                raw_html="<html>conteudo</html>",
                raw_text="conteudo aprovado",
                method=ScrapingMethod.BEAUTIFULSOUP,
                status_code=200,
                technical_score=1.0,
                text_score=1.0,
                evidence_score=1.0,
                quality_score=1.0,
                content_hash=sha256(b"cache test content").hexdigest(),
            )
            await results.save(scraping_result)

            within_window = await results.get_recent_by_url(
                job.url, since=utc_now() - timedelta(days=3)
            )
            outside_window = await results.get_recent_by_url(
                job.url, since=utc_now() + timedelta(seconds=1)
            )
            different_url = await results.get_recent_by_url(
                "https://other-url.example", since=utc_now() - timedelta(days=3)
            )

            assert within_window is not None
            assert within_window.id == scraping_result.id
            assert outside_window is None
            assert different_url is None
        finally:
            await session.close()
            await transaction.rollback()

    await engine.dispose()
