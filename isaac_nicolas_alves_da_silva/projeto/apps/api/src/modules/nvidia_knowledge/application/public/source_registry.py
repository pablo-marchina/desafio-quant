"""Contrato publico para consultar fontes NVIDIA Knowledge V2."""

from abc import ABC, abstractmethod

from apps.api.src.modules.nvidia_knowledge.application.dto import (
    ListNvidiaKnowledgeSourcesInput,
    NvidiaKnowledgeSourceView,
)


class NvidiaKnowledgeSourceRegistry(ABC):
    """Expoe as fontes oficiais/estrategicas planejadas para ingestao."""

    @abstractmethod
    async def list_sources(
        self,
        registry_input: ListNvidiaKnowledgeSourcesInput,
    ) -> list[NvidiaKnowledgeSourceView]:
        """Lista fontes filtraveis por prioridade, tecnologia ou busca."""
