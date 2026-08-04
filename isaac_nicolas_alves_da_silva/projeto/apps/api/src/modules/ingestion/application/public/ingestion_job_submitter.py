"""Contrato publico para submeter e acompanhar jobs de ingestion.

Mesmo padrao de ``scraping/application/public/job_submitter.py``: DTOs
com apenas tipos primitivos, para que o consumidor (``orchestration``)
nunca precise importar o vocabulario interno de ``ingestion``.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from apps.api.src.modules.ingestion.application.dto import CreateIngestionJobInput
from apps.api.src.modules.ingestion.domain.enums import DocumentSourceType
from apps.api.src.modules.ingestion.application.use_cases.create_ingestion_job import (
    CreateIngestionJob,
)
from apps.api.src.modules.ingestion.application.use_cases.get_ingestion_job import (
    GetIngestionJob,
)


@dataclass(frozen=True)
class IngestionJobStatusView:
    job_id: UUID
    status: str
    source_type: str
    document_id: UUID | None
    error_message: str | None


class IngestionJobSubmitter(ABC):
    """Submete um scraping_result para ingestion e permite acompanhar o job."""

    @abstractmethod
    async def submit(
        self,
        scraping_result_id: UUID,
        *,
        source_type: str = "startup_evidence",
    ) -> UUID:
        """Cria um job de ingestion e devolve seu id."""

    @abstractmethod
    async def get_status(self, job_id: UUID) -> IngestionJobStatusView:
        """Consulta o status atual do job."""


class DefaultIngestionJobSubmitter(IngestionJobSubmitter):
    """Implementacao que delega para os casos de uso ja existentes."""

    def __init__(
        self,
        *,
        create_ingestion_job: CreateIngestionJob,
        get_ingestion_job: GetIngestionJob,
    ) -> None:
        self._create_ingestion_job = create_ingestion_job
        self._get_ingestion_job = get_ingestion_job

    async def submit(
        self,
        scraping_result_id: UUID,
        *,
        source_type: str = "startup_evidence",
    ) -> UUID:
        view = await self._create_ingestion_job.execute(
            CreateIngestionJobInput(
                scraping_result_id=scraping_result_id,
                source_type=DocumentSourceType(source_type),
            )
        )
        return view.id

    async def get_status(self, job_id: UUID) -> IngestionJobStatusView:
        view = await self._get_ingestion_job.execute(job_id=job_id)
        return IngestionJobStatusView(
            job_id=view.id,
            status=view.status.value,
            source_type=view.source_type.value,
            document_id=view.document_id,
            error_message=view.error_message,
        )
