"""Portas de saida do modulo NVIDIA Knowledge."""

from abc import ABC, abstractmethod
from uuid import UUID


class NvidiaKnowledgeUrlIngestionSubmitter(ABC):
    """Contrato para submeter URLs oficiais NVIDIA a orquestracao de ingestao."""

    @abstractmethod
    async def submit(
        self,
        url: str,
        *,
        source_type: str,
    ) -> UUID:
        """Cria um job URL -> scraping -> ingestion -> embeddings."""
