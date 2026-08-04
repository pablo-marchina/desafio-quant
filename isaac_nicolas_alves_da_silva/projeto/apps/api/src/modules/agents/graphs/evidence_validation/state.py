"""Estado compartilhado do Evidence Validation Graph.

No LangGraph, cada node recebe um estado e devolve uma atualizacao parcial.
Esse ``TypedDict`` descreve quais chaves podem circular pelo grafo.
"""

from typing import TypedDict

from apps.api.src.modules.agents.application.dto import (
    EvidenceValidationInput,
    EvidenceValidationResult,
)


class EvidenceValidationState(TypedDict, total=False):
    """Estado minimo usado na V2 do agente de validacao."""

    investigation_input: EvidenceValidationInput
    prepared_context: str
    llm_result: EvidenceValidationResult
    result: EvidenceValidationResult
