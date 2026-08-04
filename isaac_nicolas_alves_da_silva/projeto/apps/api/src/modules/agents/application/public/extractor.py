"""Contrato publico do Extraction Agent."""

from abc import ABC, abstractmethod

from apps.api.src.modules.agents.application.dto import (
    ExtractionInput,
    ExtractionResult,
)


class ExtractionService(ABC):
    """Extrai dados estruturados (founders/funding/customers) de evidencias."""

    @abstractmethod
    async def extract(
        self,
        extraction_input: ExtractionInput,
        *,
        thread_id: str | None = None,
    ) -> ExtractionResult:
        """Recebe o perfil/evidencias e devolve os dados extraidos.

        ``thread_id`` e o identificador do AgentRun usado pelo checkpointer
        para salvar o estado do grafo entre nodes. Quando ausente, o grafo
        executa sem checkpoint.
        """

    async def resume(
        self,
        thread_id: str,
        resume_value: object,
    ) -> ExtractionResult:
        """Retoma uma extracao pausada por interrupt() no grafo.

        Implementacao padrao lanca NotImplementedError. Esta versao do
        grafo nao usa interrupt(), mas o metodo existe para manter o
        mesmo contrato dos demais agentes.
        """
        raise NotImplementedError(
            f"{type(self).__name__} nao suporta retomada de execucao."
        )
