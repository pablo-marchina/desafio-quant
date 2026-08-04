"""Contratos de persistencia do modulo startups."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.startups.domain.entities import Startup, StartupEvidence
from apps.api.src.modules.startups.domain.enums import AiMaturityLevel


class StartupRepository(ABC):

    @abstractmethod
    async def save(self, startup: Startup) -> None:
        """Cria ou atualiza uma startup."""

    @abstractmethod
    async def get_by_id(self, startup_id: UUID) -> Startup | None:
        """Busca startup por id."""

    @abstractmethod
    async def list_page(
        self,
        *,
        page: int,
        page_size: int,
        query: str | None = None,
        sector: str | None = None,
        country: str | None = None,
        ai_maturity_level: AiMaturityLevel | None = None,
    ) -> tuple[list[Startup], int]:
        """Lista startups filtradas, ordenadas pela atualizacao mais recente."""

    @abstractmethod
    async def list_all(self) -> list[Startup]:
        """Lista todas as startups, sem paginacao.

        Usado pela checagem de duplicata em `CreateStartup`
        (`domain/policies.py::find_duplicate_startup`) — volume do projeto
        (case/demo) nao justifica busca fuzzy indexada no banco.
        """

    @abstractmethod
    async def count_by_maturity(self) -> dict[str, int]:
        """Retorna contagem de startups por ai_maturity_level.

        Chave: valor do enum (ex. "ai_native"), incluindo None mapeado para "unclassified".
        """


class StartupEvidenceRepository(ABC):

    @abstractmethod
    async def save(self, evidence: StartupEvidence) -> None:
        """Cria ou atualiza uma evidencia."""

    @abstractmethod
    async def get_by_id(self, evidence_id: UUID) -> StartupEvidence | None:
        """Busca evidencia por id."""

    @abstractmethod
    async def list_by_startup_id(self, startup_id: UUID) -> list[StartupEvidence]:
        """Lista evidencias associadas a uma startup."""
