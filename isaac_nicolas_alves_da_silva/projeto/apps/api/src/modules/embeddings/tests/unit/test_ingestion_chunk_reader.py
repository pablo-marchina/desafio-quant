"""Testes do adapter IngestionChunkReader."""

from uuid import uuid4

import pytest

from apps.api.src.modules.embeddings.infrastructure.ingestion_adapters.ingestion_chunk_reader import (
    IngestionChunkReader,
)
from apps.api.src.modules.ingestion.domain.enums import DocumentSourceType
from apps.api.src.modules.ingestion.application.public.ingested_reader import (
    ChunkRecord,
    IngestedDocumentReader,
    IngestedDocumentSummary,
)


class FakeIngestedDocumentReader(IngestedDocumentReader):
    def __init__(self, *, chunks: list[ChunkRecord]) -> None:
        self._chunks = chunks

    async def get_by_scraping_result_id(self, scraping_result_id):
        return None

    async def list_chunks_by_document_id(self, document_id):
        return [chunk for chunk in self._chunks if chunk.document_id == document_id]


@pytest.mark.anyio
async def test_maps_chunk_records_to_chunk_source_items() -> None:
    document_id = uuid4()
    chunk_record = ChunkRecord(
        id=uuid4(),
        document_id=document_id,
        text="texto do chunk",
        source_url="https://startup.example.com",
        source_type=DocumentSourceType.NVIDIA_KNOWLEDGE,
    )
    reader = IngestionChunkReader(
        FakeIngestedDocumentReader(chunks=[chunk_record])
    )

    items = await reader.list_chunks(document_id)

    assert len(items) == 1
    assert items[0].chunk_id == chunk_record.id
    assert items[0].text == "texto do chunk"
    assert items[0].source_url == "https://startup.example.com"
    assert items[0].source_type == "nvidia_knowledge"


@pytest.mark.anyio
async def test_returns_empty_list_when_no_chunks() -> None:
    reader = IngestionChunkReader(FakeIngestedDocumentReader(chunks=[]))

    items = await reader.list_chunks(uuid4())

    assert items == []
