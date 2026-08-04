"""Contrato publico para consultar o catalogo NVIDIA."""

from abc import ABC, abstractmethod

from apps.api.src.modules.nvidia_knowledge.application.dto import (
    ListNvidiaTechnologiesInput,
    NvidiaTechnologyView,
)


class NvidiaTechnologyCatalog(ABC):
    """Catalogo consultavel por recommendations e agents futuros."""

    @abstractmethod
    async def list_technologies(
        self,
        catalog_input: ListNvidiaTechnologiesInput,
    ) -> list[NvidiaTechnologyView]:
        """Lista tecnologias NVIDIA relevantes."""

    @abstractmethod
    async def get_technology(self, slug: str) -> NvidiaTechnologyView:
        """Retorna uma tecnologia NVIDIA por slug."""
