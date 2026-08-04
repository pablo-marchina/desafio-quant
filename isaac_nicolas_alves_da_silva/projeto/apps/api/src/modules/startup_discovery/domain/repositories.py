"""Contratos de persistencia do modulo startup_discovery."""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.startup_discovery.domain.entities import (
    DiscoveryRun,
    DiscoverySubmission,
    StartupDiscoveryCandidate,
)
from apps.api.src.modules.startup_discovery.domain.enums import CandidateStatus


class DiscoveryRunRepository(ABC):

    @abstractmethod
    async def save(self, run: DiscoveryRun) -> None:
        """Cria ou atualiza um discovery run."""

    @abstractmethod
    async def get_by_id(self, run_id: UUID) -> DiscoveryRun | None:
        """Busca discovery run por id."""

    @abstractmethod
    async def list_recent(self, *, limit: int = 20) -> list[DiscoveryRun]:
        """Lista os runs mais recentes, do mais novo para o mais antigo."""

    @abstractmethod
    async def save_submission(self, submission: DiscoverySubmission) -> None:
        """Cria ou atualiza uma submissao de candidato descoberta."""

    @abstractmethod
    async def list_submissions_for_run(
        self,
        run_id: UUID,
    ) -> list[DiscoverySubmission]:
        """Lista candidatos submetidos por run."""


class CandidateRepository(ABC):

    @abstractmethod
    async def save(self, candidate: StartupDiscoveryCandidate) -> None:
        """Cria ou atualiza um candidato descoberto."""

    @abstractmethod
    async def get_by_id(self, candidate_id: UUID) -> StartupDiscoveryCandidate | None:
        """Busca candidato por id."""

    @abstractmethod
    async def list_by_run_id(self, run_id: UUID) -> list[StartupDiscoveryCandidate]:
        """Lista candidatos de um run."""

    @abstractmethod
    async def list_by_status(
        self,
        status: CandidateStatus,
        *,
        limit: int = 100,
    ) -> list[StartupDiscoveryCandidate]:
        """Lista candidatos em determinado status."""
