"""Testes do caso de uso de resposta RAG com citacoes."""

from uuid import uuid4

import pytest

from apps.api.src.modules.rag.application.dto import (
    AnswerQuestionInput,
    EvidenceChunkView,
    GenerateRagAnswerInput,
    RagAnswerView,
    RagCitationView,
    SearchEvidenceInput,
    SearchEvidenceView,
)
from apps.api.src.modules.rag.application.use_cases.answer_question import (
    AnswerQuestion,
)
from apps.api.src.modules.rag.domain.exceptions import (
    RagAnswerServiceUnavailableError,
    RagEvidenceNotFoundError,
)


class FakeRetriever:
    def __init__(self, results: list[EvidenceChunkView]) -> None:
        self.results = results
        self.last_input: SearchEvidenceInput | None = None

    async def search(self, search_input: SearchEvidenceInput) -> SearchEvidenceView:
        self.last_input = search_input
        return SearchEvidenceView(query=search_input.query.strip(), results=self.results)


class FakeAnswerGenerator:
    def __init__(self) -> None:
        self.last_input: GenerateRagAnswerInput | None = None
        self.calls = 0

    async def generate(self, answer_input: GenerateRagAnswerInput) -> RagAnswerView:
        self.calls += 1
        self.last_input = answer_input
        evidence = answer_input.evidences[0]
        return RagAnswerView(
            query=answer_input.query,
            answer="A startup tem tracao validada pela evidencia recuperada.",
            citations=[
                RagCitationView(
                    chunk_id=evidence.chunk_id,
                    document_id=evidence.document_id,
                    source_url=evidence.source_url,
                    quote="tracao validada",
                )
            ],
            evidences=answer_input.evidences,
        )


def make_evidence() -> EvidenceChunkView:
    return EvidenceChunkView(
        chunk_id=uuid4(),
        document_id=uuid4(),
        source_url="https://example.com/startup",
        text="A startup reportou tracao validada por clientes enterprise.",
        score=0.92,
    )


@pytest.mark.anyio
async def test_answer_question_retrieves_evidence_and_generates_answer() -> None:
    evidence = make_evidence()
    retriever = FakeRetriever([evidence])
    generator = FakeAnswerGenerator()
    use_case = AnswerQuestion(search_evidence=retriever, answer_generator=generator)

    view = await use_case.execute(
        AnswerQuestionInput(
            query="  Qual a tracao?  ",
            limit=3,
            source_type="startup_evidence",
        )
    )

    assert view.answer.startswith("A startup tem tracao")
    assert view.citations[0].chunk_id == evidence.chunk_id
    assert view.evidences == [evidence]
    assert retriever.last_input == SearchEvidenceInput(
        query="  Qual a tracao?  ",
        limit=3,
        source_type="startup_evidence",
    )
    assert generator.last_input == GenerateRagAnswerInput(
        query="Qual a tracao?",
        evidences=[evidence],
    )


@pytest.mark.anyio
async def test_answer_question_raises_when_no_evidence_is_found() -> None:
    retriever = FakeRetriever([])
    generator = FakeAnswerGenerator()
    use_case = AnswerQuestion(search_evidence=retriever, answer_generator=generator)

    with pytest.raises(RagEvidenceNotFoundError):
        await use_case.execute(AnswerQuestionInput(query="Pergunta sem base"))

    assert generator.calls == 0


@pytest.mark.anyio
async def test_answer_question_raises_when_generator_is_unavailable() -> None:
    retriever = FakeRetriever([make_evidence()])
    use_case = AnswerQuestion(search_evidence=retriever, answer_generator=None)

    with pytest.raises(RagAnswerServiceUnavailableError):
        await use_case.execute(AnswerQuestionInput(query="Qual a tese?"))

    assert retriever.last_input is None
