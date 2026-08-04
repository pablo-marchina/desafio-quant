"""Contrato publico do Startup Classifier Agent."""

from abc import ABC, abstractmethod

from apps.api.src.modules.agents.application.dto import (
    StartupClassificationInput,
    StartupClassificationResult,
)


class StartupClassifierService(ABC):
    """Classifica a maturidade de IA de uma startup a partir de evidencias."""

    @abstractmethod
    async def classify(
        self,
        classification_input: StartupClassificationInput,
        *,
        thread_id: str | None = None,
    ) -> StartupClassificationResult:
        """Recebe o perfil/evidencias e devolve a classificacao final.

        ``thread_id`` e o identificador do AgentRun usado pelo checkpointer
        para salvar o estado do grafo entre nodes. Quando ausente, o grafo
        executa sem checkpoint.
        """

    async def resume(
        self,
        thread_id: str,
        resume_value: object,
    ) -> StartupClassificationResult:
        """Retoma uma classificacao pausada por interrupt() no grafo.

        Implementacao padrao lanca NotImplementedError. Esta versao do
        grafo nao usa interrupt(), mas o metodo existe para manter o
        mesmo contrato dos demais agentes.
        """
        raise NotImplementedError(
            f"{type(self).__name__} nao suporta retomada de execucao."
        )
