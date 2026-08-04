"""Mapper entre Chunk e ChunkModel."""

from apps.api.src.modules.ingestion.domain.entities import Chunk
from apps.api.src.modules.ingestion.infrastructure.database.models.chunk_model import (
    ChunkModel,
)


class ChunkMapper:

    @staticmethod
    def to_model(entity: Chunk) -> ChunkModel:
        return ChunkModel(
            id=entity.id,
            document_id=entity.document_id,
            chunk_index=entity.chunk_index,
            text=entity.text,
            word_count=entity.word_count,
            char_count=entity.char_count,
            created_at=entity.created_at,
        )

    @staticmethod
    def to_entity(model: ChunkModel) -> Chunk:
        return Chunk(
            id=model.id,
            document_id=model.document_id,
            chunk_index=model.chunk_index,
            text=model.text,
            word_count=model.word_count,
            char_count=model.char_count,
            created_at=model.created_at,
        )

    @staticmethod
    def update_model(model: ChunkModel, entity: Chunk) -> None:
        model.document_id = entity.document_id
        model.chunk_index = entity.chunk_index
        model.text = entity.text
        model.word_count = entity.word_count
        model.char_count = entity.char_count
