"""Portas que conectam a aplicacao de briefing a outros modulos.

``briefing`` mantem seu proprio vocabulario (``StartupSnapshot``,
``EvidenceSnapshot``, ``RecommendationSnapshot``). As implementacoes
concretas destas portas vivem em ``infrastructure/`` e sao o unico lugar que
conhece os contratos publicos de ``startups`` e ``recommendations``.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.briefing.application.dto import (
    BriefingView,
    GroundedContext,
    RecommendationSnapshot,
    StartupProfileSnapshot,
)


class StartupProfileSource(ABC):
    """Contrato para ler o perfil de uma startup e suas evidencias."""

    @abstractmethod
    async def get_profile(self, startup_id: UUID) -> StartupProfileSnapshot:
        """Retorna a startup e suas evidencias, ou levanta erro de dominio."""


class RecommendationsSource(ABC):
    """Contrato para ler as recomendacoes NVIDIA de uma startup."""

    @abstractmethod
    async def list_by_startup(self, startup_id: UUID) -> list[RecommendationSnapshot]:
        """Lista as recomendacoes mais recentes da startup."""


class NvidiaContextGrounder(ABC):
    """Fundamenta o briefing com uma sintese de setor sobre conteudo NVIDIA real.

    Best-effort por desenho, mesmo espirito de
    ``recommendations.application.ports.NvidiaKnowledgeGrounder``:
    implementacoes nunca levantam excecao, devolvem ``None`` quando a
    fundamentacao nao for possivel - quem chama omite a secao no briefing.
    """

    @abstractmethod
    async def ground(
        self, sector: str | None, technology_names: tuple[str, ...]
    ) -> GroundedContext | None:
        """Busca conteudo NVIDIA real relevante para o setor/tecnologias."""


class BriefingDocumentRenderer(ABC):
    """Renderiza o conteudo Markdown do briefing como PDF.

    Diferente de ``NvidiaContextGrounder`` (best-effort, devolve ``None``),
    esta porta nao tem fallback: falha de renderizacao e' erro real
    (``BriefingRenderingError``), nao degradacao graciosa - o usuario pediu
    um arquivo e precisa saber se ele nao foi gerado.
    """

    @abstractmethod
    async def render_pdf(self, briefing: BriefingView) -> bytes:
        """Converte o Markdown do briefing em bytes de um PDF."""
