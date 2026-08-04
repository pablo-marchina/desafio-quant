"""Testes integrados dos repositorios de embeddings contra PostgreSQL.

Cria as linhas de scraping_jobs/scraping_results/ingestion_jobs/documents/
chunks via SQL textual (sem importar repositorios de outros modulos, mesmo
dentro de um teste) so para satisfazer as foreign keys de
embedding_jobs/embedding_job_chunks.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.database.relational.session import engine
from apps.api.src.modules.embeddings.domain.entities import EmbeddingJob, EmbeddingJobChunk
from apps.api.src.modules.embeddings.domain.enums import EmbeddingJobChunkStatus
from apps.api.src.modules.embeddings.infrastructure.database.repositories.postgres_embedding_job_chunk_repository import (
    PostgresEmbeddingJobChunkRepository,
)
from apps.api.src.modules.embeddings.infrastructure.database.repositories.postgres_embedding_job_repository import (
    PostgresEmbeddingJobRepository,
)

_INSERT_SCRAPING_JOB = text("""
    INSERT INTO scraping_jobs (id, url, status, created_at)
    VALUES (:id, :url, 'completed', now())
""")

_INSERT_SCRAPING_RESULT = text("""
    INSERT INTO scraping_results (
        id, job_id, url, final_url, title, raw_html, raw_text, method,
        status_code, technical_score, text_score, evidence_score,
        quality_score, content_hash, created_at
    ) VALUES (
        :id, :job_id, :url, :url, 'Startup Example', '<html></html>', 'raw text',
        'bs4', 200, 1.0, 1.0, 1.0, 1.0, :content_hash, now()
    )
""")

_INSERT_INGESTION_JOB = text("""
    INSERT INTO ingestion_jobs (id, scraping_result_id, status, created_at, started_at)
    VALUES (:id, :scraping_result_id, 'completed', now(), now())
""")

_INSERT_DOCUMENT = text("""
    INSERT INTO documents (
        id, ingestion_job_id, scraping_result_id, url, title, clean_text,
        word_count, chunk_count, created_at
    ) VALUES (
        :id, :ingestion_job_id, :scraping_result_id, :url, 'Startup Example',
        'texto limpo', 2, 1, now()
    )
""")

_INSERT_CHUNK = text("""
    INSERT INTO chunks (id, document_id, chunk_index, text, word_count, char_count, created_at)
    VALUES (:id, :document_id, 0, 'chunk 0', 2, 7, now())
""")


@pytest.mark.anyio
async def test_postgres_embedding_repositories_persist_job_and_chunks() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)

        try:
            scraping_job_id = uuid4()
            scraping_result_id = uuid4()
            ingestion_job_id = uuid4()
            document_id = uuid4()
            chunk_id = uuid4()

            await session.execute(
                _INSERT_SCRAPING_JOB,
                {"id": scraping_job_id, "url": "https://startup.example.com"},
            )
            await session.execute(
                _INSERT_SCRAPING_RESULT,
                {
                    "id": scraping_result_id,
                    "job_id": scraping_job_id,
                    "url": "https://startup.example.com",
                    "content_hash": uuid4().hex,
                },
            )
            await session.execute(
                _INSERT_INGESTION_JOB,
                {"id": ingestion_job_id, "scraping_result_id": scraping_result_id},
            )
            await session.execute(
                _INSERT_DOCUMENT,
                {
                    "id": document_id,
                    "ingestion_job_id": ingestion_job_id,
                    "scraping_result_id": scraping_result_id,
                    "url": "https://startup.example.com",
                },
            )
            await session.execute(
                _INSERT_CHUNK, {"id": chunk_id, "document_id": document_id}
            )
            await session.flush()

            job_repo = PostgresEmbeddingJobRepository(session)
            chunk_repo = PostgresEmbeddingJobChunkRepository(session)

            job = EmbeddingJob(document_id=document_id)
            job.start(total_chunks=1)
            await job_repo.save(job)

            chunk = EmbeddingJobChunk(job_id=job.id, chunk_id=chunk_id)
            chunk.record_failure("erro transitorio")
            await chunk_repo.save(chunk)
            chunk.complete(
                model_name="fake-test",
                vector_dimension=2,
                input_char_count=7,
                estimated_input_tokens=2,
                latency_ms=10,
                content_hash="hash",
            )
            await chunk_repo.save(chunk)

            job.record_metrics_from_chunks([chunk])
            job.finish(succeeded=1, failed=0)
            await job_repo.save(job)

            restored_job = await job_repo.get_by_id(job.id)
            restored_chunks = await chunk_repo.list_by_job_id(job.id)

            assert restored_job is not None
            assert restored_job.total_chunks == 1
            assert restored_job.succeeded_chunks == 1
            assert restored_job.total_latency_ms == 10
            assert restored_job.status.value == "completed"

            assert len(restored_chunks) == 1
            assert restored_chunks[0].status is EmbeddingJobChunkStatus.COMPLETED
            assert restored_chunks[0].attempt_count == 1
            assert restored_chunks[0].model_name == "fake-test"
        finally:
            await session.close()
            await transaction.rollback()

    await engine.dispose()


@pytest.mark.anyio
async def test_find_completed_by_content_hash_filters_by_hash_and_model() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)

        try:
            scraping_job_id = uuid4()
            scraping_result_id = uuid4()
            ingestion_job_id = uuid4()
            document_id = uuid4()
            chunk_id = uuid4()

            await session.execute(
                _INSERT_SCRAPING_JOB,
                {"id": scraping_job_id, "url": "https://startup.example.com"},
            )
            await session.execute(
                _INSERT_SCRAPING_RESULT,
                {
                    "id": scraping_result_id,
                    "job_id": scraping_job_id,
                    "url": "https://startup.example.com",
                    "content_hash": uuid4().hex,
                },
            )
            await session.execute(
                _INSERT_INGESTION_JOB,
                {"id": ingestion_job_id, "scraping_result_id": scraping_result_id},
            )
            await session.execute(
                _INSERT_DOCUMENT,
                {
                    "id": document_id,
                    "ingestion_job_id": ingestion_job_id,
                    "scraping_result_id": scraping_result_id,
                    "url": "https://startup.example.com",
                },
            )
            await session.execute(
                _INSERT_CHUNK, {"id": chunk_id, "document_id": document_id}
            )
            await session.flush()

            chunk_repo = PostgresEmbeddingJobChunkRepository(session)
            job = EmbeddingJob(document_id=document_id)
            job.start(total_chunks=1)
            await PostgresEmbeddingJobRepository(session).save(job)

            chunk = EmbeddingJobChunk(job_id=job.id, chunk_id=chunk_id)
            chunk.complete(
                model_name="gemini-embedding-001",
                vector_dimension=3,
                input_char_count=7,
                estimated_input_tokens=2,
                latency_ms=5,
                content_hash="shared-hash",
            )
            await chunk_repo.save(chunk)

            found = await chunk_repo.find_completed_by_content_hash(
                "shared-hash", model_name="gemini-embedding-001"
            )
            wrong_model = await chunk_repo.find_completed_by_content_hash(
                "shared-hash", model_name="other-model"
            )
            wrong_hash = await chunk_repo.find_completed_by_content_hash(
                "unrelated-hash", model_name="gemini-embedding-001"
            )

            assert found is not None
            assert found.chunk_id == chunk_id
            assert wrong_model is None
            assert wrong_hash is None
        finally:
            await session.close()
            await transaction.rollback()

    await engine.dispose()
