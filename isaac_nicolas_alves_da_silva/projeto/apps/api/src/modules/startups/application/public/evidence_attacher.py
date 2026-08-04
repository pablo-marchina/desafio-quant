"""Contrato publico para anexar evidencia a uma startup a partir de outro modulo."""

from abc import ABC, abstractmethod
from uuid import UUID


class EvidenceAttacher(ABC):
    """Anexacao de evidencia consumivel por orchestration e outros modulos."""

    @abstractmethod
    async def attach_evidence(
        self,
        *,
        startup_id: UUID,
        scraping_result_id: UUID,
        source_url: str,
        title: str | None = None,
        notes: str | None = None,
    ) -> None:
        """Associa uma evidencia aprovada a uma startup."""
