"""Caso de uso para responder pergunta com citacoes."""

from apps.api.src.modules.rag.application.dto import (
    AnswerQuestionInput,
    GenerateRagAnswerInput,
    RagAnswerView,
    SearchEvidenceInput,
)
from apps.api.src.modules.rag.application.public.answer_generator import (
    RagAnswerGenerator,
)
from apps.api.src.modules.rag.application.public.question_answerer import (
    RagQuestionAnswerer,
)
from apps.api.src.modules.rag.application.public.retriever import (
    Retriever,
)
from apps.api.src.modules.rag.domain.exceptions import (
    RagAnswerServiceUnavailableError,
    RagEvidenceNotFoundError,
)


class AnswerQuestion(RagQuestionAnswerer):
    """Recupera evidencias e gera resposta fundamentada."""

    def __init__(
        self,
        *,
        search_evidence: Retriever,
        answer_generator: RagAnswerGenerator | None,
    ) -> None:
        self._search_evidence = search_evidence
        self._answer_generator = answer_generator

    async def answer(self, answer_input: AnswerQuestionInput) -> RagAnswerView:
        if self._answer_generator is None:
            raise RagAnswerServiceUnavailableError(
                "Servico de resposta RAG nao configurado (verifique GEMINI_API_KEY)."
            )

        search_view = await self._search_evidence.search(
            SearchEvidenceInput(
                query=answer_input.query,
                limit=answer_input.limit,
                source_type=answer_input.source_type,
                document_ids=answer_input.document_ids,
            )
        )
        if not search_view.results:
            raise RagEvidenceNotFoundError(
                "Nao ha evidencias recuperadas suficientes para responder."
            )

        return await self._answer_generator.generate(
            GenerateRagAnswerInput(
                query=search_view.query,
                evidences=search_view.results,
            )
        )

    async def execute(self, answer_input: AnswerQuestionInput) -> RagAnswerView:
        """Alias mantido para a rota `/rag/answer` existente."""

        return await self.answer(answer_input)
