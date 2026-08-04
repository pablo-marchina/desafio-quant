"""Portas do modulo agents.

Portas sao contratos que a camada de aplicacao usa para falar com capacidades
externas. Aqui, o agents precisa publicar execucoes longas em fila, mas nao
deve conhecer Redis ou Dramatiq diretamente. Tambem usa portas para chamar
outros modulos como "tool" (ex: NVIDIA RAG Agent chamando ``rag``), mantendo
``agents`` sem dependencia direta dos DTOs do modulo externo.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from apps.api.src.modules.agents.application.dto import (
    NvidiaRagResult,
    RecommendationCandidate,
    SearchExecutionResult,
)


class AgentTaskDispatcher(ABC):
    """Contrato para enviar uma execucao de agente a um worker externo."""

    @abstractmethod
    async def dispatch(
        self,
        *,
        run_id: UUID,
    ) -> None:
        """Publica somente o identificador da execucao para o worker."""


class SearchExecutorPort(ABC):
    """Contrato para transformar uma query planejada em URLs candidatas.

    O Search Planner Agent gera apenas texto; esta porta representa o provedor
    externo de busca web (ex: Tavily), mantendo o restante do modulo sem
    conhecer HTTP, API key ou formato do fornecedor.
    """

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        excluded_urls: list[str] | None = None,
    ) -> SearchExecutionResult:
        """Executa a query e devolve URLs candidatas normalizadas."""


class NvidiaRagToolPort(ABC):
    """Contrato interno para consultar a base de conhecimento NVIDIA via RAG.

    Vocabulario simplificado e proprio de ``agents`` (so query/limit na
    entrada, ``NvidiaRagResult`` na saida) — decoupled das DTOs exatas de
    ``rag``. A traducao e responsabilidade do adaptador concreto
    (``infrastructure/rag_adapters/``).
    """

    @abstractmethod
    async def answer(self, query: str, *, limit: int = 5) -> NvidiaRagResult:
        """Recupera evidencias da base NVIDIA e devolve resposta com citacoes."""


class RecommendationToolPort(ABC):
    """Contrato interno para gerar recomendacoes deterministicas como tool.

    Vocabulario simplificado e proprio de ``agents`` — decoupled das DTOs
    exatas de ``recommendations``. A traducao e responsabilidade do
    adaptador concreto (``infrastructure/recommendations_adapters/``).
    """

    @abstractmethod
    async def generate(self, startup_id: UUID) -> list[RecommendationCandidate]:
        """Gera as recomendacoes deterministicas mais recentes da startup."""

    @abstractmethod
    async def update_justifications(
        self, startup_id: UUID, justifications: dict[str, str]
    ) -> None:
        """Persiste a justificativa revisada por tecnologia (technology_slug)."""


class RecommendationReviewerPort(ABC):
    """Contrato interno para revisar candidatos de recomendacao via LLM.

    So entra em jogo depois que ``RecommendationToolPort.generate()`` ja
    produziu candidatos deterministicos — o LLM nao gera recomendacoes do
    zero, so julga candidatos ambiguos e melhora a redacao da justificativa.
    """

    @abstractmethod
    async def review(
        self, candidates: list[RecommendationCandidate]
    ) -> list[RecommendationCandidate]:
        """Devolve os candidatos revisados (ambiguos descartaveis, todos com
        justificativa em linguagem de negocio)."""


class BriefingToolPort(ABC):
    """Contrato interno para gerar o briefing deterministico como tool.

    Vocabulario simplificado e proprio de ``agents`` — devolve so o
    Markdown (``content``), decoupled do ``BriefingView`` exato de
    ``briefing``. A traducao e responsabilidade do adaptador concreto
    (``infrastructure/briefing_adapters/``).
    """

    @abstractmethod
    async def generate(self, startup_id: UUID) -> str:
        """Gera o briefing deterministico (Markdown) mais recente da startup."""

    @abstractmethod
    async def update_content(self, startup_id: UUID, content: str) -> UUID:
        """Persiste a prosa reescrita no briefing mais recente da startup
        e devolve o id do briefing atualizado."""


class BriefingProseRewriterPort(ABC):
    """Contrato interno para reescrever a prosa do briefing via LLM.

    So entra em jogo depois que ``BriefingToolPort.generate()`` ja
    produziu o Markdown deterministico — o LLM nao monta secoes nem decide
    riscos/proximas acoes, so reescreve a prosa em linguagem executiva.
    """

    @abstractmethod
    async def rewrite(self, content: str) -> str:
        """Reescreve a prosa em linguagem executiva, preservando citacoes.

        Implementacoes devem devolver ``content`` inalterado (fallback
        seguro) quando a reescrita nao preservar todas as citacoes do
        original — nunca confiar so no prompt para isso.
        """
