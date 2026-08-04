"""Contrato publico para submeter e acompanhar jobs de embeddings.

Mesmo padrao de ``scraping``/``ingestion``. Este e' o ultimo passo da
pipeline scraping->ingestion->embeddings — por isso o DTO de status nao
tem um ponteiro "para o proximo recurso" (``EmbeddingJobStatus.PARTIAL``
conta como concluido: os chunks que deram certo ja bastam para o
restante do sistema, mesmo padrao de tolerancia ja usado dentro do
proprio ``ExecuteEmbeddingJob``).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from apps.api.src.modules.embeddings.application.dto import CreateEmbeddingJobInput
from apps.api.src.modules.embeddings.application.use_cases.create_embedding_job import (
    CreateEmbeddingJob,
)
from apps.api.src.modules.embeddings.application.use_cases.get_embedding_job import (
    GetEmbeddingJob,
)


@dataclass(frozen=True)
class EmbeddingJobStatusView:
    job_id: UUID
    status: str
    error_message: str | None


class EmbeddingJobSubmitter(ABC):
    """Submete um document_id para embeddings e permite acompanhar o job."""

    @abstractmethod
    async def submit(self, document_id: UUID) -> UUID:
        """Cria um job de embeddings e devolve seu id."""

    @abstractmethod
    async def get_status(self, job_id: UUID) -> EmbeddingJobStatusView:
        """Consulta o status atual do job."""


class DefaultEmbeddingJobSubmitter(EmbeddingJobSubmitter):
    """Implementacao que delega para os casos de uso ja existentes."""

    def __init__(
        self,
        *,
        create_embedding_job: CreateEmbeddingJob,
        get_embedding_job: GetEmbeddingJob,
    ) -> None:
        self._create_embedding_job = create_embedding_job
        self._get_embedding_job = get_embedding_job

    async def submit(self, document_id: UUID) -> UUID:
        view = await self._create_embedding_job.execute(
            CreateEmbeddingJobInput(document_id=document_id)
        )
        return view.id

    async def get_status(self, job_id: UUID) -> EmbeddingJobStatusView:
        view = await self._get_embedding_job.execute(job_id=job_id)
        return EmbeddingJobStatusView(
            job_id=view.id,
            status=view.status.value,
            error_message=view.error_message,
        )
