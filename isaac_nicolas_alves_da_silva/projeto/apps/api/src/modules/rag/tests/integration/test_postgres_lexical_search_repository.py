"""Testes integrados do PostgresLexicalSearchRepository contra PostgreSQL.

Mesmo padrao de `ingestion/tests/integration/test_postgres_ingested_document_reader.py`:
``PostgresLexicalSearchRepository`` abre e fecha sua propria sessao por
chamada, entao o setup usa commit real + limpeza via CASCADE a partir de
``scraping_jobs``.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.src.modules.ingestion.domain.enums import DocumentSourceType
from apps.api.src.database.relational.session import AsyncSessionFactory, engine
from apps.api.src.modules.ingestion.domain.entities import (
    Chunk,
    Document,
    IngestionJob,
    document_content_hash,
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
from apps.api.src.modules.rag.infrastructure.database.postgres_lexical_search_repository import (
    PostgresLexicalSearchRepository,
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
async def test_lexical_search_finds_chunk_by_websearch_query() -> None:
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
            content_hash=document_content_hash("texto limpo do documento"),
            source_type=DocumentSourceType.NVIDIA_KNOWLEDGE,
        )
        await PostgresDocumentRepository(session).save(document)

        chunk_repo = PostgresChunkRepository(session)
        matching_chunk = Chunk(
            document_id=document.id,
            chunk_index=0,
            text="A startup treina modelos proprios de inteligencia artificial generativa.",
            word_count=9,
            char_count=73,
        )
        unrelated_chunk = Chunk(
            document_id=document.id,
            chunk_index=1,
            text="A empresa vende sapatos em loja fisica.",
            word_count=7,
            char_count=40,
        )
        await chunk_repo.save(matching_chunk)
        await chunk_repo.save(unrelated_chunk)

        await session.commit()

        repository = PostgresLexicalSearchRepository()
        results = await repository.search("inteligencia artificial generativa", limit=5)
        filtered_results = await repository.search(
            "inteligencia artificial generativa",
            limit=5,
            source_type="nvidia_knowledge",
        )
        unrelated_results = await repository.search(
            "inteligencia artificial generativa",
            limit=5,
            source_type="startup_evidence",
        )

        assert any(result.chunk_id == matching_chunk.id for result in results)
        assert all(result.chunk_id != unrelated_chunk.id for result in results)
        assert any(result.chunk_id == matching_chunk.id for result in filtered_results)
        assert all(result.chunk_id != matching_chunk.id for result in unrelated_results)
    finally:
        await session.execute(_DELETE_SCRAPING_JOB, {"id": scraping_job_id})
        await session.commit()
        await session.close()
        await engine.dispose()
