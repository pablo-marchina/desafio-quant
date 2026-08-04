"""Contratos de persistencia do modulo de embeddings."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.embeddings.domain.entities import (
    EmbeddingJob,
    EmbeddingJobChunk,
)


class EmbeddingJobRepository(ABC):

    @abstractmethod
    async def save(self, job: EmbeddingJob) -> None:
        """Cria ou atualiza um job."""

    @abstractmethod
    async def get_by_id(self, job_id: UUID) -> EmbeddingJob | None:
        """Retorna o job ou ``None``."""


class EmbeddingJobChunkRepository(ABC):

    @abstractmethod
    async def save(self, chunk: EmbeddingJobChunk) -> None:
        """Cria ou atualiza o status de um chunk dentro de um job."""

    @abstractmethod
    async def list_by_job_id(self, job_id: UUID) -> list[EmbeddingJobChunk]:
        """Lista todos os chunks rastreados de um job."""

    @abstractmethod
    async def find_completed_by_content_hash(
        self, content_hash: str, *, model_name: str
    ) -> EmbeddingJobChunk | None:
        """Busca um chunk ja completado com o mesmo hash de conteudo e modelo.

        O filtro por ``model_name`` evita reusar um vetor gerado por um
        modelo de embedding diferente do atualmente configurado.
        """
