"""Adaptador que fundamenta justificativas usando o contrato publico de `rag`.

Nao importa nada de `rag` alem de `application/public/` e `application/dto.py`
- a instancia de `RagQuestionAnswerer` e' construida pela `RagFactory` e
injetada aqui. Filtra sempre por `source_type="nvidia_knowledge"`.

Best-effort por desenho (ver `NvidiaKnowledgeGrounder`): qualquer falha do
RAG (sem API key, sem evidencia, erro do provedor) ou resposta sem citacao
real (evidencia insuficiente, ver `RagAnswerView.citations` vazio) devolve
`None` em vez de propagar excecao - quem chama cai pro template
deterministico de hoje.
"""

from apps.api.src.modules.recommendations.application.dto import (
    GroundedJustification,
)
from apps.api.src.modules.recommendations.application.ports import (
    NvidiaKnowledgeGrounder,
)
from apps.api.src.modules.rag.application.dto import AnswerQuestionInput
from apps.api.src.modules.rag.application.public.question_answerer import (
    RagQuestionAnswerer,
)
from apps.api.src.modules.rag.domain.exceptions import RagError

NVIDIA_KNOWLEDGE_SOURCE_TYPE = "nvidia_knowledge"


class RagNvidiaKnowledgeGrounder(NvidiaKnowledgeGrounder):

    def __init__(self, question_answerer: RagQuestionAnswerer) -> None:
        self._question_answerer = question_answerer

    async def ground(
        self, technology_name: str, use_case: str
    ) -> GroundedJustification | None:
        try:
            view = await self._question_answerer.answer(
                AnswerQuestionInput(
                    query=f"How can NVIDIA {technology_name} help with {use_case}?",
                    source_type=NVIDIA_KNOWLEDGE_SOURCE_TYPE,
                    limit=5,
                )
            )
        except RagError:
            return None

        if not view.citations:
            return None

        return GroundedJustification(
            text=view.answer,
            citation_urls=tuple(
                dict.fromkeys(citation.source_url for citation in view.citations)
            ),
        )
