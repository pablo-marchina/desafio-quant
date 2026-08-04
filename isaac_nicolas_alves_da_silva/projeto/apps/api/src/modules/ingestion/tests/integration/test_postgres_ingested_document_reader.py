"""Testes integrados do PostgresIngestedDocumentReader contra PostgreSQL.

``PostgresIngestedDocumentReader`` abre e fecha sua propria sessao por
chamada (mesmo padrao de ``PostgresScrapingResultReader``), entao o setup
aqui usa commit real + limpeza manual no final (via CASCADE a partir de
``scraping_jobs``), em vez do padrao "uma transacao, rollback no final"
usado pelos outros testes integrados — compartilhar a mesma sessao com o
reader nao funcionaria, pois ele fecharia a sessao apos a primeira chamada.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.src.database.relational.session import AsyncSessionFactory, engine
from apps.api.src.modules.ingestion.domain.entities import Chunk, Document, IngestionJob
from apps.api.src.modules.ingestion.infrastructure.database.postgres_ingested_document_reader import (
    PostgresIngestedDocumentReader,
)
from apps.api.src.modules.ingestion.infrastructure.database.repositories.postgres_chunk_repository import (
    PostgresChunkRepository,
)
from apps.api.src.modules.ingestion.infrastructure.database.repositories.postgres_document_repository import (
    PostgresDocumentRepository,
)
from apps.api.src.modules.ingestion.infrastructure.database.repositories.postgres_ingestion_job_repository import (
    PostgresIngestionJobRepository,
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

_DELETE_SCRAPING_JOB = text("DELETE FROM scraping_jobs WHERE id = :id")


@pytest.mark.anyio
async def test_reader_lists_chunks_and_summary_for_real_document() -> None:
    scraping_job_id = uuid4()
    scraping_result_id = uuid4()

    session = AsyncSessionFactory()
    try:
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

        job = IngestionJob(scraping_result_id=scraping_result_id)
        job.start()
        await PostgresIngestionJobRepository(session).save(job)

        document = Document(
            ingestion_job_id=job.id,
            scraping_result_id=scraping_result_id,
            url="https://startup.example.com",
            title="Startup Example",
            clean_text="texto limpo do documento",
            word_count=4,
            chunk_count=2,
            content_hash="testhash0001",
        )
        await PostgresDocumentRepository(session).save(document)

        chunk_repo = PostgresChunkRepository(session)
        for i in range(2):
            await chunk_repo.save(
                Chunk(
                    document_id=document.id,
                    chunk_index=i,
                    text=f"chunk {i}",
                    word_count=2,
                    char_count=7,
                )
            )

        await session.commit()

        reader = PostgresIngestedDocumentReader()

        summary = await reader.get_by_scraping_result_id(scraping_result_id)
        assert summary is not None
        assert summary.url == "https://startup.example.com"
        assert summary.chunk_count == 2

        records = await reader.list_chunks_by_document_id(document.id)
        assert len(records) == 2
        assert {r.text for r in records} == {"chunk 0", "chunk 1"}
        assert all(r.source_url == "https://startup.example.com" for r in records)
    finally:
        await session.execute(_DELETE_SCRAPING_JOB, {"id": scraping_job_id})
        await session.commit()
        await session.close()
        await engine.dispose()
