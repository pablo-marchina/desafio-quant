"""Contratos de repositorio do modulo NVIDIA Knowledge."""

from abc import ABC, abstractmethod

from apps.api.src.modules.nvidia_knowledge.domain.entities import (
    NvidiaKnowledgeSource,
    NvidiaTechnology,
)
from apps.api.src.modules.nvidia_knowledge.domain.enums import (
    NvidiaKnowledgeSourcePriority,
    NvidiaTechnologyCategory,
)


class NvidiaTechnologyRepository(ABC):
    """Repositorio de tecnologias NVIDIA."""

    @abstractmethod
    async def list_all(
        self,
        *,
        category: NvidiaTechnologyCategory | None = None,
        query: str | None = None,
    ) -> list[NvidiaTechnology]:
        """Lista tecnologias, opcionalmente filtradas."""

    @abstractmethod
    async def get_by_slug(self, slug: str) -> NvidiaTechnology | None:
        """Busca uma tecnologia por slug."""


class NvidiaKnowledgeSourceRepository(ABC):
    """Repositorio de fontes planejadas para NVIDIA Knowledge V2."""

    @abstractmethod
    async def list_all(
        self,
        *,
        priority: NvidiaKnowledgeSourcePriority | None = None,
        technology_slug: str | None = None,
        query: str | None = None,
    ) -> list[NvidiaKnowledgeSource]:
        """Lista fontes de conhecimento, opcionalmente filtradas."""
