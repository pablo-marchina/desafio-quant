"""Contrato publico para responder perguntas com citacoes (RAG)."""

from abc import ABC, abstractmethod

from apps.api.src.modules.rag.application.dto import (
    AnswerQuestionInput,
    RagAnswerView,
)


class RagQuestionAnswerer(ABC):
    """Responde uma pergunta usando busca hibrida + citacoes."""

    @abstractmethod
    async def answer(self, answer_input: AnswerQuestionInput) -> RagAnswerView:
        """Recupera evidencias e gera uma resposta fundamentada com citacoes."""
