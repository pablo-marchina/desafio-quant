"""Testes do RagNvidiaContextGrounder."""

from uuid import uuid4

import pytest

from apps.api.src.modules.briefing.infrastructure.rag_adapters.nvidia_context_grounder_adapter import (
    RagNvidiaContextGrounder,
)
from apps.api.src.modules.rag.application.dto import (
    AnswerQuestionInput,
    RagAnswerView,
    RagCitationView,
)
from apps.api.src.modules.rag.application.public.question_answerer import (
    RagQuestionAnswerer,
)
from apps.api.src.modules.rag.domain.exceptions import RagEvidenceNotFoundError


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
async def test_ground_translates_answer_with_citations_into_grounded_context() -> None:
    view = RagAnswerView(
        query="How can NVIDIA technologies like NVIDIA NIM help an AI company in the fintech sector?",
        answer="NVIDIA NIM acelera atendimento via LLM no setor fintech.",
        citations=[
            RagCitationView(
                chunk_id=uuid4(),
                document_id=uuid4(),
                source_url="https://nvidia.com/nim",
                quote="NIM accelerates LLM-based customer service.",
            )
        ],
        evidences=[],
    )
    answerer = FakeQuestionAnswerer(view=view)
    grounder = RagNvidiaContextGrounder(answerer)

    result = await grounder.ground("fintech", ("NVIDIA NIM",))

    assert result is not None
    assert result.text == view.answer
    assert result.citation_urls == ("https://nvidia.com/nim",)
    assert answerer.received_input is not None
    assert answerer.received_input.source_type == "nvidia_knowledge"
    assert "fintech" in answerer.received_input.query


@pytest.mark.anyio
async def test_ground_uses_generic_query_without_sector() -> None:
    view = RagAnswerView(
        query="...",
        answer="NVIDIA NIM ajuda startups de IA em geral.",
        citations=[
            RagCitationView(
                chunk_id=uuid4(),
                document_id=uuid4(),
                source_url="https://nvidia.com/nim",
                quote="...",
            )
        ],
        evidences=[],
    )
    answerer = FakeQuestionAnswerer(view=view)
    grounder = RagNvidiaContextGrounder(answerer)

    result = await grounder.ground(None, ("NVIDIA NIM",))

    assert result is not None
    assert answerer.received_input is not None
    assert "sector" not in answerer.received_input.query


@pytest.mark.anyio
async def test_ground_returns_none_without_technology_names() -> None:
    answerer = FakeQuestionAnswerer()
    grounder = RagNvidiaContextGrounder(answerer)

    result = await grounder.ground("fintech", ())

    assert result is None
    assert answerer.received_input is None


@pytest.mark.anyio
async def test_ground_returns_none_when_rag_raises_error() -> None:
    answerer = FakeQuestionAnswerer(error=RagEvidenceNotFoundError("sem evidencia"))
    grounder = RagNvidiaContextGrounder(answerer)

    result = await grounder.ground("fintech", ("NVIDIA NIM",))

    assert result is None


@pytest.mark.anyio
async def test_ground_returns_none_when_answer_has_no_citations() -> None:
    view = RagAnswerView(
        query="...",
        answer="As evidencias fornecidas nao contem informacoes suficientes.",
        citations=[],
        evidences=[],
    )
    answerer = FakeQuestionAnswerer(view=view)
    grounder = RagNvidiaContextGrounder(answerer)

    result = await grounder.ground("fintech", ("NVIDIA NIM",))

    assert result is None
