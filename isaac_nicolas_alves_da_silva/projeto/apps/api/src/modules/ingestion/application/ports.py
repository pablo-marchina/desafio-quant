"""Portas (interfaces) do módulo de ingestion."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.ingestion.application.dto import ScrapingResultData


class ScrapingResultReader(ABC):
    """Porta para ler scraping_results sem importar internals do módulo scraping."""

    @abstractmethod
    async def get_by_id(self, result_id: UUID) -> ScrapingResultData | None:
        """Retorna os dados de um scraping_result ou ``None``."""


class IngestionTaskDispatcher(ABC):
    """Porta para publicar jobs de ingestion na fila."""

    @abstractmethod
    async def dispatch(self, *, job_id: UUID) -> None:
        """Publica o job_id na fila de ingestion."""
