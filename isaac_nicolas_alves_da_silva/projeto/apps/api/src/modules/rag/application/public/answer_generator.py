"""Contrato publico para gerar respostas RAG."""

from abc import ABC, abstractmethod

from apps.api.src.modules.rag.application.dto import (
    GenerateRagAnswerInput,
    RagAnswerView,
)


class RagAnswerGenerator(ABC):
    """Gera resposta fundamentada a partir de evidencias recuperadas."""

    @abstractmethod
    async def generate(self, answer_input: GenerateRagAnswerInput) -> RagAnswerView:
        """Gera uma resposta com citacoes estruturadas."""
