"""Repositorio PostgreSQL para Chunk."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.ingestion.domain.entities import Chunk
from apps.api.src.modules.ingestion.domain.repositories import ChunkRepository
from apps.api.src.modules.ingestion.infrastructure.database.mappers.chunk_mapper import (
    ChunkMapper,
)
from apps.api.src.modules.ingestion.infrastructure.database.models.chunk_model import (
    ChunkModel,
)


class PostgresChunkRepository(ChunkRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, chunk: Chunk) -> None:
        model = await self._session.get(ChunkModel, chunk.id)
        if model is None:
            self._session.add(ChunkMapper.to_model(chunk))
        else:
            ChunkMapper.update_model(model, chunk)
        await self._session.flush()

    async def list_by_document_id(self, document_id: UUID) -> list[Chunk]:
        models = await self._session.scalars(
            select(ChunkModel)
            .where(ChunkModel.document_id == document_id)
            .order_by(ChunkModel.chunk_index)
        )
        return [ChunkMapper.to_entity(m) for m in models]
