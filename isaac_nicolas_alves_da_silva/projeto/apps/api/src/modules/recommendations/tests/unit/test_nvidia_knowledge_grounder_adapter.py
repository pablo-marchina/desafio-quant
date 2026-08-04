"""Testes do RagNvidiaKnowledgeGrounder."""

from uuid import uuid4

import pytest

from apps.api.src.modules.rag.application.dto import (
    AnswerQuestionInput,
    RagAnswerView,
    RagCitationView,
)
from apps.api.src.modules.rag.application.public.question_answerer import (
    RagQuestionAnswerer,
)
from apps.api.src.modules.rag.domain.exceptions import RagEvidenceNotFoundError
from apps.api.src.modules.recommendations.infrastructure.rag_adapters.nvidia_knowledge_grounder_adapter import (
    RagNvidiaKnowledgeGrounder,
)


class FakeQuestionAnswerer(RagQuestionAnswerer):
    def __init__(self, view: RagAnswerView | None = None, error: Exception | None = None) -> None:
        self._view = view
        self._error = error
        self.received_input: AnswerQuestionInput | None = None

    async def answer(self, answer_input: AnswerQuestionInput) -> RagAnswerView:
        self.received_input = answer_input
        if self._error is not None:
            raise self._error
        assert self._view is not None
        return self._view


@pytest.mark.anyio
async def test_ground_translates_answer_with_citations_into_grounded_justification() -> None:
    view = RagAnswerView(
        query="How can NVIDIA NIM help with model serving?",
        answer="NVIDIA NIM simplifica o deploy de microservicos de inferencia.",
        citations=[
            RagCitationView(
                chunk_id=uuid4(),
                document_id=uuid4(),
                source_url="https://nvidia.com/nim",
                quote="NIM microservices simplify inference deployment.",
            )
        ],
        evidences=[],
    )
    answerer = FakeQuestionAnswerer(view=view)
    grounder = RagNvidiaKnowledgeGrounder(answerer)

    result = await grounder.ground("NVIDIA NIM", "model serving")

    assert result is not None
    assert result.text == view.answer
    assert result.citation_urls == ("https://nvidia.com/nim",)
    assert answerer.received_input is not None
    assert answerer.received_input.source_type == "nvidia_knowledge"
    assert "NVIDIA NIM" in answerer.received_input.query


@pytest.mark.anyio
async def test_ground_returns_none_when_rag_raises_error() -> None:
    answerer = FakeQuestionAnswerer(error=RagEvidenceNotFoundError("sem evidencia"))
    grounder = RagNvidiaKnowledgeGrounder(answerer)

    result = await grounder.ground("MONAI", "medical imaging")

    assert result is None


@pytest.mark.anyio
async def test_ground_returns_none_when_answer_has_no_citations() -> None:
    view = RagAnswerView(
        query="How can NVIDIA MONAI help with medical imaging?",
        answer="As evidencias fornecidas nao contem informacoes suficientes.",
        citations=[],
        evidences=[],
    )
    answerer = FakeQuestionAnswerer(view=view)
    grounder = RagNvidiaKnowledgeGrounder(answerer)

    result = await grounder.ground("MONAI", "medical imaging")

    assert result is None
