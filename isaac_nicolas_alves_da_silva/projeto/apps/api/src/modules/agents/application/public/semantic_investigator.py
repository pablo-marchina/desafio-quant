"""Contrato publico do Evidence Validation Agent.

Este e o UNICO arquivo do modulo ``agents`` que outros modulos podem
importar. Ele define a interface; a implementacao concreta (hoje, uma
chamada a Gemini em ``infrastructure/llm/gemini_evidence_validator.py``; no
futuro, um grafo LangGraph completo em ``graphs/evidence_validation/``) e
escolhida pela ``factories/agents_factory.py``.

O nome do arquivo (``semantic_investigator``) reflete o nome que o modulo
``scraping`` usa para a porta equivalente
(``scraping/application/ports.py -> SemanticInvestigator``), facilitando a
leitura cruzada entre os dois modulos.
"""

from abc import ABC, abstractmethod

from apps.api.src.modules.agents.application.dto import (
    EvidenceValidationInput,
    EvidenceValidationResult,
)


class EvidenceValidationService(ABC):
    """Investiga conteudo que a revisao semantica simples nao conseguiu decidir."""

    @abstractmethod
    async def investigate(
        self,
        investigation_input: EvidenceValidationInput,
        *,
        thread_id: str | None = None,
    ) -> EvidenceValidationResult:
        """Recebe o contexto apurado e devolve uma decisao final fundamentada.

        ``thread_id`` e o identificador do AgentRun usado pelo checkpointer para
        salvar o estado do grafo entre nodes. Quando ausente, o grafo executa
        sem checkpoint (comportamento V5).
        """

    async def resume(
        self,
        thread_id: str,
        resume_value: object,
    ) -> EvidenceValidationResult:
        """Retoma uma investigacao pausada por interrupt() no grafo.

        Implementacao padrao lanca NotImplementedError. Servicos sem
        checkpointer (ex: fakes de teste) nao precisam sobrescrever.
        """

        raise NotImplementedError(
            f"{type(self).__name__} nao suporta retomada de execucao."
        )
