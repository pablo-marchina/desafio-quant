"""Contrato publico para submeter e acompanhar jobs de scraping.

Primeiro contrato publico do modulo ``scraping`` — at e' aqui, qualquer
modulo que quisesse acionar scraping precisava ir pela rota HTTP. Os
DTOs usam apenas tipos primitivos, de proposito: nenhum modulo
consumidor (hoje, ``orchestration``) precisa importar o vocabulario
interno (``JobStatus`` etc) de ``scraping``.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from apps.api.src.modules.scraping.application.use_cases.create_scraping_job import (
    CreateScrapingJob,
)
from apps.api.src.modules.scraping.application.use_cases.get_scraping_job import (
    GetScrapingJob,
)


@dataclass(frozen=True)
class ScrapingJobStatusView:
    job_id: UUID
    status: str
    result_id: UUID | None
    error_message: str | None


class ScrapingJobSubmitter(ABC):
    """Submete uma URL para scraping e permite consultar o andamento."""

    @abstractmethod
    async def submit(self, url: str, *, source_type: str = "startup_evidence") -> UUID:
        """Cria um job de scraping para a URL e devolve seu id.

        ``source_type`` identifica a origem do conteudo (ex:
        "nvidia_knowledge" para fontes curadas do registry). O valor padrao
        preserva o comportamento de scraping de evidencia de startup.
        """

    @abstractmethod
    async def get_status(self, job_id: UUID) -> ScrapingJobStatusView:
        """Consulta o status atual do job."""


class DefaultScrapingJobSubmitter(ScrapingJobSubmitter):
    """Implementacao que delega para os casos de uso ja existentes."""

    def __init__(
        self,
        *,
        create_scraping_job: CreateScrapingJob,
        get_scraping_job: GetScrapingJob,
    ) -> None:
        self._create_scraping_job = create_scraping_job
        self._get_scraping_job = get_scraping_job

    async def submit(self, url: str, *, source_type: str = "startup_evidence") -> UUID:
        job = await self._create_scraping_job.execute(url, source_type=source_type)
        return job.id

    async def get_status(self, job_id: UUID) -> ScrapingJobStatusView:
        details = await self._get_scraping_job.execute(job_id)
        job = details.job
        return ScrapingJobStatusView(
            job_id=job.id,
            status=job.status.value,
            result_id=job.result_id,
            error_message=job.error_message,
        )
