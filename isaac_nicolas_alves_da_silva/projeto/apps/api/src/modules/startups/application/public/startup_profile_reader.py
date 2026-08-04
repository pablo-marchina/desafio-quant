"""Contrato publico para ler o perfil consolidado de uma startup."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.startups.application.dto import StartupProfileView


class StartupProfileReader(ABC):
    """Perfil consultavel por recommendations e outros modulos futuros."""

    @abstractmethod
    async def get_profile(self, startup_id: UUID) -> StartupProfileView:
        """Retorna a startup e suas evidencias associadas."""
