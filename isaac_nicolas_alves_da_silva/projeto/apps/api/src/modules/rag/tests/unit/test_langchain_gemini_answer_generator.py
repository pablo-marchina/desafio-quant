"""Testes do gerador Gemini RAG."""

from uuid import uuid4

from apps.api.src.modules.rag.application.dto import (
    EvidenceChunkView,
    GenerateRagAnswerInput,
)
from apps.api.src.modules.rag.infrastructure.llm.langchain_gemini_answer_generator import (
    GeminiRagAnswerResponse,
    GeminiRagCitationResponse,
    LangChainGeminiRagAnswerGenerator,
    MAX_RAG_CITATION_QUOTE_CHARACTERS,
    MAX_RAG_CITATIONS,
)


def test_to_view_truncates_extra_llm_citations() -> None:
    chunk_id = uuid4()
    evidence = EvidenceChunkView(
        chunk_id=chunk_id,
        document_id=uuid4(),
        source_url="https://example.com/nvidia",
        text="TensorRT-LLM optimizes inference for large language models.",
        score=0.9,
        source_type="nvidia_knowledge",
    )
    parsed = GeminiRagAnswerResponse(
        answer="TensorRT-LLM optimizes LLM inference.",
        citations=[
            GeminiRagCitationResponse(
                chunk_id=str(chunk_id),
                quote=f"supporting quote {index}",
            )
            for index in range(MAX_RAG_CITATIONS + 1)
        ],
    )
    generator = LangChainGeminiRagAnswerGenerator.__new__(
        LangChainGeminiRagAnswerGenerator
    )

    view = generator._to_view(
        GenerateRagAnswerInput(query="What is TensorRT-LLM optimized for?", evidences=[evidence]),
        parsed,
    )

    assert len(view.citations) == MAX_RAG_CITATIONS
    assert view.citations[-1].quote == f"supporting quote {MAX_RAG_CITATIONS - 1}"


def test_to_view_truncates_long_llm_citation_quotes() -> None:
    chunk_id = uuid4()
    evidence = EvidenceChunkView(
        chunk_id=chunk_id,
        document_id=uuid4(),
        source_url="https://example.com/nvidia",
        text="NVIDIA Inception offers benefits for startups.",
        score=0.9,
        source_type="nvidia_knowledge",
    )
    parsed = GeminiRagAnswerResponse(
        answer="NVIDIA Inception offers startup benefits.",
        citations=[
            GeminiRagCitationResponse(
                chunk_id=str(chunk_id),
                quote="x" * (MAX_RAG_CITATION_QUOTE_CHARACTERS + 1),
            )
        ],
    )
    generator = LangChainGeminiRagAnswerGenerator.__new__(
        LangChainGeminiRagAnswerGenerator
    )

    view = generator._to_view(
        GenerateRagAnswerInput(query="What benefits does Inception offer?", evidences=[evidence]),
        parsed,
    )

    assert len(view.citations[0].quote) == MAX_RAG_CITATION_QUOTE_CHARACTERS


def test_to_view_accepts_one_based_evidence_index_as_citation_id() -> None:
    evidences = [
        EvidenceChunkView(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source_url=f"https://example.com/nvidia/{index}",
            text=f"Evidence {index}",
            score=0.9,
            source_type="nvidia_knowledge",
        )
        for index in range(3)
    ]
    parsed = GeminiRagAnswerResponse(
        answer="The answer is supported by the third evidence.",
        citations=[
            GeminiRagCitationResponse(
                chunk_id="3",
                quote="Evidence 2",
            )
        ],
    )
    generator = LangChainGeminiRagAnswerGenerator.__new__(
        LangChainGeminiRagAnswerGenerator
    )

    view = generator._to_view(
        GenerateRagAnswerInput(query="Question?", evidences=evidences),
        parsed,
    )

    assert view.citations[0].chunk_id == evidences[2].chunk_id
