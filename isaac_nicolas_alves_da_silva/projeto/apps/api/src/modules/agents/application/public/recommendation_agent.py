"""Contrato publico do Recommendation Agent."""

from abc import ABC, abstractmethod

from apps.api.src.modules.agents.application.dto import (
    RecommendationAgentInput,
    RecommendationAgentResult,
)


class RecommendationAgentService(ABC):
    """Gera recomendacoes de tecnologia NVIDIA para uma startup, com revisao."""

    @abstractmethod
    async def recommend(
        self,
        recommendation_input: RecommendationAgentInput,
        *,
        thread_id: str | None = None,
    ) -> RecommendationAgentResult:
        """Recebe a startup e devolve as recomendacoes revisadas.

        ``thread_id`` e o identificador do AgentRun usado pelo checkpointer
        para salvar o estado do grafo entre nodes. Quando ausente, o grafo
        executa sem checkpoint.
        """

    async def resume(
        self,
        thread_id: str,
        resume_value: object,
    ) -> RecommendationAgentResult:
        """Retoma uma recomendacao pausada por interrupt() no grafo.

        Implementacao padrao lanca NotImplementedError. Esta versao do
        grafo nao usa interrupt(), mas o metodo existe para manter o
        mesmo contrato dos demais agentes.
        """
        raise NotImplementedError(
            f"{type(self).__name__} nao suporta retomada de execucao."
        )
