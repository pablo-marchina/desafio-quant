"""Adaptador que implementa NvidiaRagToolPort usando o contrato publico do rag.

Nao importa nada de ``rag`` alem de ``application/public/`` e
``application/dto.py`` — a instancia de ``RagQuestionAnswerer`` e' construida
pela ``RagFactory`` e injetada aqui. Filtra sempre por
``source_type="nvidia_knowledge"``: este e' o NVIDIA RAG Agent, nao um
agente generico de RAG.
"""

from apps.api.src.modules.agents.application.dto import (
    NvidiaRagCitation,
    NvidiaRagResult,
)
from apps.api.src.modules.agents.application.ports import NvidiaRagToolPort
from apps.api.src.modules.agents.domain.exceptions import AgentRagQueryError
from apps.api.src.modules.rag.application.dto import AnswerQuestionInput
from apps.api.src.modules.rag.application.public.question_answerer import (
    RagQuestionAnswerer,
)
from apps.api.src.modules.rag.domain.exceptions import RagError

NVIDIA_KNOWLEDGE_SOURCE_TYPE = "nvidia_knowledge"


class RagQuestionAnswererAdapter(NvidiaRagToolPort):

    def __init__(self, question_answerer: RagQuestionAnswerer) -> None:
        self._question_answerer = question_answerer

    async def answer(self, query: str, *, limit: int = 5) -> NvidiaRagResult:
        try:
            view = await self._question_answerer.answer(
                AnswerQuestionInput(
                    query=query,
                    limit=limit,
                    source_type=NVIDIA_KNOWLEDGE_SOURCE_TYPE,
                )
            )
        except RagError as error:
            raise AgentRagQueryError(
                f"Consulta a base NVIDIA via RAG falhou: {error}"
            ) from error

        return NvidiaRagResult(
            answer=view.answer,
            citations=[
                NvidiaRagCitation(
                    source_url=citation.source_url,
                    quote=citation.quote,
                )
                for citation in view.citations
            ],
        )
