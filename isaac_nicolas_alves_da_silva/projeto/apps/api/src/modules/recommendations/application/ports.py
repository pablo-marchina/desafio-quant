"""Portas que conectam a aplicacao de recommendations a outros modulos.

``recommendations`` mantem seu proprio vocabulario (``StartupProfileSnapshot``,
``NvidiaTechnologySnapshot``). As implementacoes concretas destas portas vivem
em ``infrastructure/`` e sao o unico lugar que conhece os contratos publicos
de ``startups`` e ``nvidia_knowledge``.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.recommendations.application.dto import (
    GroundedJustification,
    NvidiaTechnologySnapshot,
    StartupProfileSnapshot,
)


class StartupProfileSource(ABC):
    """Contrato para ler o perfil de uma startup."""

    @abstractmethod
    async def get_profile(self, startup_id: UUID) -> StartupProfileSnapshot:
        """Retorna o perfil da startup ou levanta erro de dominio se ausente."""


class NvidiaCatalogSource(ABC):
    """Contrato para ler o catalogo de tecnologias NVIDIA."""

    @abstractmethod
    async def list_technologies(self) -> list[NvidiaTechnologySnapshot]:
        """Lista todas as tecnologias disponiveis para o motor de regras."""


class NvidiaKnowledgeGrounder(ABC):
    """Fundamenta a justificativa de uma recomendacao em conteudo NVIDIA real.

    Best-effort por desenho: implementacoes nunca levantam excecao, devolvem
    ``None`` quando a fundamentacao nao for possivel (sem API key, sem
    evidencia suficiente, falha do provedor) - quem chama cai pro template
    deterministico de hoje nesse caso.
    """

    @abstractmethod
    async def ground(
        self, technology_name: str, use_case: str
    ) -> GroundedJustification | None:
        """Busca conteudo NVIDIA real sobre a tecnologia e o caso de uso."""


class NvidiaSemanticCandidateSelector(ABC):
    """Pre-seleciona candidatos NVIDIA plausiveis via retrieval semantico.

    Dado o texto da startup (setor + descricao + evidencias), busca chunks
    do nvidia_knowledge no Qdrant e identifica quais tecnologias do catalogo
    aparecem no conteudo recuperado.

    Best-effort por desenho: implementacoes nunca propagam excecao.
    ``set`` vazio = nenhum candidato identificado via semantica; quem chama
    deve tratar como sinal de fallback (usar todos os candidatos).
    """

    @abstractmethod
    async def select(
        self,
        query: str,
        technology_keywords: dict[str, tuple[str, ...]],
    ) -> set[str]:
        """Retorna slugs cujo conteudo NVIDIA apareceu no retrieval semantico.

        Args:
            query: Texto combinado da startup (setor + descricao + evidencias).
            technology_keywords: {slug: keywords} do catalogo, para mapear
                chunks recuperados para tecnologias especificas.
        Returns:
            Conjunto de slugs confirmados via retrieval. Vazio = sem resultado
            semantico (caller deve usar todos os candidatos como fallback).
        """
