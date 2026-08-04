"""Entidades do domínio do módulo de ingestion."""

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .enums import DocumentSourceType, IngestionJobStatus
from .exceptions import InvalidIngestionJobTransitionError


def document_content_hash(clean_text: str) -> str:
    """SHA-256 hex do texto limpo — usado para dedup de Document por conteudo."""
    return hashlib.sha256(clean_text.encode()).hexdigest()


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class IngestionJob:
    """Representa o processo de transformar um scraping_result em documento limpo."""

    scraping_result_id: UUID
    source_type: DocumentSourceType = DocumentSourceType.STARTUP_EVIDENCE

    id: UUID = field(default_factory=uuid4)
    status: IngestionJobStatus = IngestionJobStatus.PENDING
    document_id: UUID | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def start(self) -> None:
        if self.status is not IngestionJobStatus.PENDING:
            raise InvalidIngestionJobTransitionError(
                f"Somente jobs pendentes podem iniciar. Estado atual: {self.status}."
            )
        self.status = IngestionJobStatus.RUNNING
        self.started_at = utc_now()

    def complete(self, document_id: UUID) -> None:
        if self.status is not IngestionJobStatus.RUNNING:
            raise InvalidIngestionJobTransitionError(
                f"Somente jobs em execucao podem concluir. Estado atual: {self.status}."
            )
        self.status = IngestionJobStatus.COMPLETED
        self.document_id = document_id
        self.finished_at = utc_now()

    def fail(self, reason: str) -> None:
        if self.status is not IngestionJobStatus.RUNNING:
            raise InvalidIngestionJobTransitionError(
                f"Somente jobs em execucao podem falhar. Estado atual: {self.status}."
            )
        self.status = IngestionJobStatus.FAILED
        self.error_message = reason
        self.finished_at = utc_now()

    def fail_dispatch(self, reason: str) -> None:
        if self.status is not IngestionJobStatus.PENDING:
            raise InvalidIngestionJobTransitionError(
                "Somente jobs pendentes podem falhar durante o dispatch."
            )
        self.status = IngestionJobStatus.FAILED
        self.error_message = reason
        self.finished_at = utc_now()


@dataclass
class Document:
    """Documento limpo e normalizado produzido a partir de um scraping_result."""

    ingestion_job_id: UUID
    scraping_result_id: UUID
    url: str
    title: str | None
    clean_text: str
    word_count: int
    chunk_count: int
    content_hash: str
    source_type: DocumentSourceType = DocumentSourceType.STARTUP_EVIDENCE

    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class Chunk:
    """Fragmento de texto de um documento, pronto para embedding."""

    document_id: UUID
    chunk_index: int
    text: str
    word_count: int
    char_count: int

    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
