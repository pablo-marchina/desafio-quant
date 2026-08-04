"""Repositorio PostgreSQL para Document."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.modules.ingestion.domain.entities import Document
from apps.api.src.modules.ingestion.domain.repositories import DocumentRepository
from apps.api.src.modules.ingestion.infrastructure.database.mappers.document_mapper import (
    DocumentMapper,
)
from apps.api.src.modules.ingestion.infrastructure.database.models.document_model import (
    DocumentModel,
)


class PostgresDocumentRepository(DocumentRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, document: Document) -> None:
        model = await self._session.get(DocumentModel, document.id)
        if model is None:
            self._session.add(DocumentMapper.to_model(document))
        else:
            DocumentMapper.update_model(model, document)
        await self._session.flush()

    async def get_by_id(self, document_id: UUID) -> Document | None:
        model = await self._session.get(DocumentModel, document_id)
        if model is None:
            return None
        return DocumentMapper.to_entity(model)

    async def find_by_content_hash(self, content_hash: str) -> Document | None:
        result = await self._session.execute(
            select(DocumentModel).where(DocumentModel.content_hash == content_hash)
        )
        model = result.scalars().first()
        if model is None:
            return None
        return DocumentMapper.to_entity(model)
