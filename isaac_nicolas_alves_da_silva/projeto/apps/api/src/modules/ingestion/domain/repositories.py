"""Contratos de persistencia do módulo de ingestion."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.ingestion.domain.entities import Chunk, Document, IngestionJob


class IngestionJobRepository(ABC):

    @abstractmethod
    async def save(self, job: IngestionJob) -> None:
        """Cria ou atualiza um job."""

    @abstractmethod
    async def get_by_id(self, job_id: UUID) -> IngestionJob | None:
        """Retorna o job ou ``None``."""

    @abstractmethod
    async def get_by_scraping_result_id(
        self, scraping_result_id: UUID
    ) -> IngestionJob | None:
        """Retorna o job associado a um scraping_result ou ``None``."""


class DocumentRepository(ABC):

    @abstractmethod
    async def save(self, document: Document) -> None:
        """Persiste um documento."""

    @abstractmethod
    async def get_by_id(self, document_id: UUID) -> Document | None:
        """Retorna o documento ou ``None``."""

    @abstractmethod
    async def find_by_content_hash(self, content_hash: str) -> Document | None:
        """Retorna um documento com o hash de conteudo dado, ou ``None``."""


class ChunkRepository(ABC):

    @abstractmethod
    async def save(self, chunk: Chunk) -> None:
        """Persiste um chunk."""

    @abstractmethod
    async def list_by_document_id(self, document_id: UUID) -> list[Chunk]:
        """Lista todos os chunks de um documento."""
