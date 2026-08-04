"""Testes do adapter RagQuestionAnswererAdapter."""

from uuid import uuid4

import pytest

from apps.api.src.modules.agents.domain.exceptions import AgentRagQueryError
from apps.api.src.modules.agents.infrastructure.rag_adapters.rag_question_answerer_adapter import (
    NVIDIA_KNOWLEDGE_SOURCE_TYPE,
    RagQuestionAnswererAdapter,
)
from apps.api.src.modules.rag.application.dto import (
    AnswerQuestionInput,
    RagAnswerView,
    RagCitationView,
)
from apps.api.src.modules.rag.domain.exceptions import RagEvidenceNotFoundError


class FakeQuestionAnswerer:
    def __init__(self, view: RagAnswerView) -> None:
        self.view = view
        self.last_input: AnswerQuestionInput | None = None

    async def answer(self, answer_input: AnswerQuestionInput) -> RagAnswerView:
        self.last_input = answer_input
        return self.view


class FailingQuestionAnswerer:
    async def answer(self, answer_input: AnswerQuestionInput) -> RagAnswerView:
        raise RagEvidenceNotFoundError("Sem evidencias.")


@pytest.mark.anyio
async def test_answer_filters_by_nvidia_knowledge_source_type() -> None:
    view = RagAnswerView(
        query="O que e NIM?",
        answer="NIM e um microservico de inferencia da NVIDIA.",
        citations=[
            RagCitationView(
                chunk_id=uuid4(),
                document_id=uuid4(),
                source_url="https://docs.nvidia.com/nim/",
                quote="NIM e um microservico de inferencia.",
            )
        ],
        evidences=[],
    )
    answerer = FakeQuestionAnswerer(view)
    adapter = RagQuestionAnswererAdapter(answerer)

    result = await adapter.answer("O que e NIM?", limit=3)

    assert answerer.last_input == AnswerQuestionInput(
        query="O que e NIM?",
        limit=3,
        source_type=NVIDIA_KNOWLEDGE_SOURCE_TYPE,
    )
    assert result.answer == view.answer
    assert result.citations == [
        type(result.citations[0])(
            source_url="https://docs.nvidia.com/nim/",
            quote="NIM e um microservico de inferencia.",
        )
    ]


@pytest.mark.anyio
async def test_answer_translates_rag_error_into_agent_error() -> None:
    adapter = RagQuestionAnswererAdapter(FailingQuestionAnswerer())

    with pytest.raises(AgentRagQueryError):
        await adapter.answer("pergunta sem base")
