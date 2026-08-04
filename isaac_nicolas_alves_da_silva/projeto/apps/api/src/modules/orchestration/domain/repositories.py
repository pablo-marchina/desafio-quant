"""Contratos de persistencia do modulo orchestration."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.orchestration.domain.entities import (
    AnalysisJob,
    UrlIngestionJob,
)
from apps.api.src.modules.orchestration.domain.enums import UrlIngestionJobStatus


class AnalysisJobRepository(ABC):

    @abstractmethod
    async def save(self, analysis_job: AnalysisJob) -> None:
        """Cria ou atualiza um analysis job."""

    @abstractmethod
    async def get_by_id(self, analysis_job_id: UUID) -> AnalysisJob | None:
        """Busca analysis job por id."""

    @abstractmethod
    async def list_by_startup_id(self, startup_id: UUID) -> list[AnalysisJob]:
        """Lista o historico de execucoes de uma startup, mais recentes primeiro."""


class UrlIngestionJobRepository(ABC):

    @abstractmethod
    async def save(self, job: UrlIngestionJob) -> None:
        """Cria ou atualiza um url ingestion job."""

    @abstractmethod
    async def get_by_id(self, job_id: UUID) -> UrlIngestionJob | None:
        """Busca url ingestion job por id."""

    @abstractmethod
    async def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: UrlIngestionJobStatus | None = None,
        source_type: str | None = None,
    ) -> tuple[list[UrlIngestionJob], int]:
        """Lista url ingestion jobs filtrados, mais recentes primeiro."""

    @abstractmethod
    async def list_completed_by_url(self, url: str) -> list[UrlIngestionJob]:
        """Lista jobs concluidos com a mesma URL, mais recentes primeiro.

        Usado para encontrar `document_id`s de scrapes anteriores da mesma
        URL e limpar seus vetores orfaos no Qdrant quando um re-scrape
        (apos o cache de `SCRAPING_RESULT_CACHE_TTL` expirar) gera um
        `Document` novo.
        """

    @abstractmethod
    async def list_by_startup_id(self, startup_id: UUID) -> list[UrlIngestionJob]:
        """Lista jobs associados a uma startup, mais recentes primeiro."""
