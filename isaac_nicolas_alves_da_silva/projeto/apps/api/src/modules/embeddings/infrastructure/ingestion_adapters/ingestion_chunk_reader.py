"""Adaptador que implementa ChunkSourceReader usando o contrato publico do ingestion.

Nao importa nada de ``ingestion`` alem de ``application/public/`` — a
instancia de ``IngestedDocumentReader`` e' construida pela
``IngestionFactory`` e injetada aqui.
"""

from uuid import UUID

from apps.api.src.modules.embeddings.application.dto import ChunkSourceItem
from apps.api.src.modules.embeddings.application.ports import ChunkSourceReader
from apps.api.src.modules.ingestion.application.public.ingested_reader import (
    IngestedDocumentReader,
)


class IngestionChunkReader(ChunkSourceReader):

    def __init__(self, ingested_document_reader: IngestedDocumentReader) -> None:
        self._ingested_document_reader = ingested_document_reader

    async def list_chunks(self, document_id: UUID) -> list[ChunkSourceItem]:
        records = await self._ingested_document_reader.list_chunks_by_document_id(
            document_id
        )
        return [
            ChunkSourceItem(
                chunk_id=record.id,
                text=record.text,
                source_url=record.source_url,
                source_type=record.source_type.value,
            )
            for record in records
        ]
