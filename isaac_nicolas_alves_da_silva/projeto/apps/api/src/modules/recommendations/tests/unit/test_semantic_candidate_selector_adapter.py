"""Testes do RagSemanticNvidiaCandidateSelector."""

from uuid import uuid4

import pytest

from apps.api.src.modules.rag.application.dto import (
    EvidenceChunkView,
    SearchEvidenceInput,
    SearchEvidenceView,
)
from apps.api.src.modules.rag.application.public.retriever import Retriever
from apps.api.src.modules.rag.domain.exceptions import RagEvidenceNotFoundError
from apps.api.src.modules.recommendations.infrastructure.rag_adapters.semantic_candidate_selector_adapter import (
    RagSemanticNvidiaCandidateSelector,
)


def _chunk(text: str) -> EvidenceChunkView:
    return EvidenceChunkView(
        chunk_id=uuid4(),
        document_id=uuid4(),
        source_url="https://docs.nvidia.com/nim",
        text=text,
        score=0.8,
        source_type="nvidia_knowledge",
    )


class FakeRetriever(Retriever):
    def __init__(
        self,
        chunks: list[EvidenceChunkView] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._chunks = chunks or []
        self._error = error
        self.received_input: SearchEvidenceInput | None = None

    async def search(self, search_input: SearchEvidenceInput) -> SearchEvidenceView:
        self.received_input = search_input
        if self._error is not None:
            raise self._error
        return SearchEvidenceView(query=search_input.query, results=self._chunks)


TECH_KEYWORDS: dict[str, tuple[str, ...]] = {
    "nvidia-nim": ("nim", "microservice", "inference endpoint"),
    "nvidia-riva": ("riva", "speech", "asr", "tts"),
    "rapids": ("rapids", "cudf", "cuml", "gpu analytics"),
}


@pytest.mark.anyio
async def test_select_returns_slug_when_keyword_appears_in_chunk() -> None:
    retriever = FakeRetriever(chunks=[_chunk("NVIDIA NIM microservice simplifies inference.")])
    selector = RagSemanticNvidiaCandidateSelector(retriever)

    result = await selector.select("startup de inferencia LLM", TECH_KEYWORDS)

    assert "nvidia-nim" in result


@pytest.mark.anyio
async def test_select_returns_multiple_slugs_when_multiple_tech_found() -> None:
    retriever = FakeRetriever(
        chunks=[
            _chunk("NIM microservice for model serving."),
            _chunk("RAPIDS cudf accelerates GPU analytics on tabular data."),
        ]
    )
    selector = RagSemanticNvidiaCandidateSelector(retriever)

    result = await selector.select("startup de dados", TECH_KEYWORDS)

    assert "nvidia-nim" in result
    assert "rapids" in result
    assert "nvidia-riva" not in result


@pytest.mark.anyio
async def test_select_returns_empty_set_when_no_keywords_match() -> None:
    retriever = FakeRetriever(
        chunks=[_chunk("Generalized transformer architecture overview.")]
    )
    selector = RagSemanticNvidiaCandidateSelector(retriever)

    result = await selector.select("startup de marketing", TECH_KEYWORDS)

    assert result == set()


@pytest.mark.anyio
async def test_select_returns_empty_set_when_no_chunks_returned() -> None:
    retriever = FakeRetriever(chunks=[])
    selector = RagSemanticNvidiaCandidateSelector(retriever)

    result = await selector.select("startup de IA", TECH_KEYWORDS)

    assert result == set()


@pytest.mark.anyio
async def test_select_returns_empty_set_when_retriever_raises_exception() -> None:
    retriever = FakeRetriever(error=RagEvidenceNotFoundError("sem conteudo"))
    selector = RagSemanticNvidiaCandidateSelector(retriever)

    result = await selector.select("startup de dados", TECH_KEYWORDS)

    assert result == set()


@pytest.mark.anyio
async def test_select_returns_empty_set_for_empty_query() -> None:
    retriever = FakeRetriever(chunks=[_chunk("RAPIDS cudf for analytics.")])
    selector = RagSemanticNvidiaCandidateSelector(retriever)

    result = await selector.select("   ", TECH_KEYWORDS)

    assert result == set()
    assert retriever.received_input is None


@pytest.mark.anyio
async def test_select_filters_by_word_boundary_not_substring() -> None:
    """'nim' em 'pseudonym' nao deve ativar nvidia-nim."""
    retriever = FakeRetriever(chunks=[_chunk("used as a pseudonym in the document.")])
    selector = RagSemanticNvidiaCandidateSelector(retriever)

    result = await selector.select("startup criativa", TECH_KEYWORDS)

    assert "nvidia-nim" not in result


@pytest.mark.anyio
async def test_select_sends_request_with_nvidia_knowledge_source_type() -> None:
    retriever = FakeRetriever(chunks=[])
    selector = RagSemanticNvidiaCandidateSelector(retriever)

    await selector.select("startup de IA", TECH_KEYWORDS)

    assert retriever.received_input is not None
    assert retriever.received_input.source_type == "nvidia_knowledge"
