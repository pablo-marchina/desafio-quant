"""Contrato publico do Briefing Agent."""

from abc import ABC, abstractmethod

from apps.api.src.modules.agents.application.dto import (
    BriefingAgentInput,
    BriefingAgentResult,
)


class BriefingAgentService(ABC):
    """Gera o briefing executivo de uma startup, com prosa revisada."""

    @abstractmethod
    async def generate(
        self,
        briefing_input: BriefingAgentInput,
        *,
        thread_id: str | None = None,
    ) -> BriefingAgentResult:
        """Recebe a startup e devolve o briefing com prosa executiva.

        ``thread_id`` e o identificador do AgentRun usado pelo checkpointer
        para salvar o estado do grafo entre nodes. Quando ausente, o grafo
        executa sem checkpoint.
        """

    async def resume(
        self,
        thread_id: str,
        resume_value: object,
    ) -> BriefingAgentResult:
        """Retoma um briefing pausado por interrupt() no grafo.

        Implementacao padrao lanca NotImplementedError. Esta versao do
        grafo nao usa interrupt(), mas o metodo existe para manter o
        mesmo contrato dos demais agentes.
        """
        raise NotImplementedError(
            f"{type(self).__name__} nao suporta retomada de execucao."
        )
