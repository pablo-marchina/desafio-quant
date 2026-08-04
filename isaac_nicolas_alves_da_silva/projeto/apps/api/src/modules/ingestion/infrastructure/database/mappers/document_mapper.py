"""Mapper entre Document e DocumentModel."""

from apps.api.src.modules.ingestion.domain.entities import Document
from apps.api.src.modules.ingestion.domain.enums import DocumentSourceType
from apps.api.src.modules.ingestion.infrastructure.database.models.document_model import (
    DocumentModel,
)


class DocumentMapper:

    @staticmethod
    def to_model(entity: Document) -> DocumentModel:
        return DocumentModel(
            id=entity.id,
            ingestion_job_id=entity.ingestion_job_id,
            scraping_result_id=entity.scraping_result_id,
            url=entity.url,
            title=entity.title,
            clean_text=entity.clean_text,
            word_count=entity.word_count,
            chunk_count=entity.chunk_count,
            content_hash=entity.content_hash,
            source_type=entity.source_type.value,
            created_at=entity.created_at,
        )

    @staticmethod
    def to_entity(model: DocumentModel) -> Document:
        return Document(
            id=model.id,
            ingestion_job_id=model.ingestion_job_id,
            scraping_result_id=model.scraping_result_id,
            url=model.url,
            title=model.title,
            clean_text=model.clean_text,
            word_count=model.word_count,
            chunk_count=model.chunk_count,
            content_hash=model.content_hash or "",
            source_type=DocumentSourceType(model.source_type),
            created_at=model.created_at,
        )

    @staticmethod
    def update_model(model: DocumentModel, entity: Document) -> None:
        model.ingestion_job_id = entity.ingestion_job_id
        model.scraping_result_id = entity.scraping_result_id
        model.url = entity.url
        model.title = entity.title
        model.clean_text = entity.clean_text
        model.word_count = entity.word_count
        model.chunk_count = entity.chunk_count
        model.content_hash = entity.content_hash
        model.source_type = entity.source_type.value
