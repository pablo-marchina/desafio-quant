"""Contrato publico do NVIDIA RAG Agent."""

from abc import ABC, abstractmethod

from apps.api.src.modules.agents.application.dto import (
    NvidiaRagInput,
    NvidiaRagResult,
)


class NvidiaRagService(ABC):
    """Consulta a base de conhecimento NVIDIA via RAG, com citacoes."""

    @abstractmethod
    async def answer(
        self,
        rag_input: NvidiaRagInput,
        *,
        thread_id: str | None = None,
    ) -> NvidiaRagResult:
        """Recebe a pergunta e devolve a resposta fundamentada na base NVIDIA.

        ``thread_id`` e o identificador do AgentRun usado pelo checkpointer
        para salvar o estado do grafo entre nodes. Quando ausente, o grafo
        executa sem checkpoint.
        """

    async def resume(
        self,
        thread_id: str,
        resume_value: object,
    ) -> NvidiaRagResult:
        """Retoma uma consulta pausada por interrupt() no grafo.

        Implementacao padrao lanca NotImplementedError. Esta versao do
        grafo nao usa interrupt(), mas o metodo existe para manter o
        mesmo contrato dos demais agentes.
        """
        raise NotImplementedError(
            f"{type(self).__name__} nao suporta retomada de execucao."
        )
