"""Adaptador que fundamenta o briefing usando o contrato publico de `rag`.

Mesmo espirito de
`recommendations/infrastructure/rag_adapters/nvidia_knowledge_grounder_adapter.py`:
nao importa nada de `rag` alem de `application/public/` e `application/dto.py`,
filtra sempre por `source_type="nvidia_knowledge"`, e e' best-effort - falha
ou resposta sem citacao real (evidencia insuficiente) devolve `None` em vez
de propagar excecao.
"""

from apps.api.src.modules.briefing.application.dto import GroundedContext
from apps.api.src.modules.briefing.application.ports import NvidiaContextGrounder
from apps.api.src.modules.rag.application.dto import AnswerQuestionInput
from apps.api.src.modules.rag.application.public.question_answerer import (
    RagQuestionAnswerer,
)
from apps.api.src.modules.rag.domain.exceptions import RagError

NVIDIA_KNOWLEDGE_SOURCE_TYPE = "nvidia_knowledge"


class RagNvidiaContextGrounder(NvidiaContextGrounder):

    def __init__(self, question_answerer: RagQuestionAnswerer) -> None:
        self._question_answerer = question_answerer

    async def ground(
        self, sector: str | None, technology_names: tuple[str, ...]
    ) -> GroundedContext | None:
        if not technology_names:
            return None

        names = ", ".join(technology_names)
        query = (
            f"How can NVIDIA technologies like {names} help an AI company "
            f"in the {sector} sector?"
            if sector
            else f"How can NVIDIA technologies like {names} help an AI startup?"
        )

        try:
            view = await self._question_answerer.answer(
                AnswerQuestionInput(
                    query=query,
                    source_type=NVIDIA_KNOWLEDGE_SOURCE_TYPE,
                    limit=5,
                )
            )
        except RagError:
            return None

        if not view.citations:
            return None

        return GroundedContext(
            text=view.answer,
            citation_urls=tuple(
                dict.fromkeys(citation.source_url for citation in view.citations)
            ),
        )
