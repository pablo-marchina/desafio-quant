"""Contrato publico para criar uma startup a partir de outro modulo."""

from abc import ABC, abstractmethod
from uuid import UUID


class StartupCreator(ABC):
    """Criacao de startup consumivel por orchestration e outros modulos."""

    @abstractmethod
    async def create_startup(
        self, *, name: str, website_url: str | None = None
    ) -> UUID:
        """Cria a startup e retorna seu id."""
