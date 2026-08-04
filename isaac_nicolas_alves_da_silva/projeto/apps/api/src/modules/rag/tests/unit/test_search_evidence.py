"""Testes do caso de uso SearchEvidence (busca hibrida + reranking)."""

from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.embeddings.application.dto import (
    ChunkEmbeddingRecord,
    ChunkSearchResult,
)
from apps.api.src.modules.embeddings.application.public.vector_repository import (
    VectorRepository,
)
from apps.api.src.modules.ingestion.application.public.ingested_reader import (
    ChunkRecord,
    IngestedDocumentReader,
    IngestedDocumentSummary,
)
from apps.api.src.modules.rag.application.dto import (
    EvidenceChunkView,
    LexicalSearchResult,
    SearchEvidenceInput,
)
from apps.api.src.modules.rag.application.ports import (
    EmbeddingGenerator,
    LexicalSearchRepository,
    Reranker,
    SupplementalEvidenceProvider,
)
from apps.api.src.modules.rag.application.use_cases.search_evidence import (
    CONTEXT_WINDOW_RADIUS,
    MIN_CANDIDATE_POOL,
    SearchEvidence,
)
from apps.api.src.modules.rag.domain.exceptions import EmptyRagQueryError


class FakeEmbeddingGenerator(EmbeddingGenerator):
    def __init__(self) -> None:
        self.received_texts: list[str] = []

    async def generate(self, text: str) -> tuple[float, ...]:
        self.received_texts.append(text)
        return (0.1, 0.2, 0.3)


class FakeVectorRepository(VectorRepository):
    def __init__(self, results: list[ChunkSearchResult]) -> None:
        self.results = results
        self.searched_vectors: list[tuple[float, ...]] = []
        self.limits: list[int] = []
        self.source_types: list[str | None] = []

    async def upsert(self, record: ChunkEmbeddingRecord) -> None:
        pass

    async def search(
        self,
        query_vector: tuple[float, ...],
        *,
        limit: int = 5,
        source_type: str | None = None,
        document_ids=None,
    ) -> list[ChunkSearchResult]:
        if document_ids is not None and len(document_ids) == 0:
            return []
        self.searched_vectors.append(query_vector)
        self.limits.append(limit)
        self.source_types.append(source_type)
        return self.results[:limit]

    async def get_by_chunk_id(self, chunk_id):
        return None

    async def delete_by_document_id(self, document_id) -> None:
        pass


class FakeLexicalSearchRepository(LexicalSearchRepository):
    def __init__(self, results: list[LexicalSearchResult] | None = None) -> None:
        self.results = results or []
        self.queries: list[str] = []
        self.limits: list[int] = []
        self.source_types: list[str | None] = []
        self.document_ids_list: list = []

    async def search(
        self,
        query: str,
        *,
        limit: int,
        source_type: str | None = None,
        document_ids=None,
    ) -> list[LexicalSearchResult]:
        if document_ids is not None and len(document_ids) == 0:
            return []
        self.queries.append(query)
        self.limits.append(limit)
        self.source_types.append(source_type)
        self.document_ids_list.append(document_ids)
        return self.results[:limit]


class FakeIngestedDocumentReader(IngestedDocumentReader):
    def __init__(self, chunks_by_document: dict[UUID, list[ChunkRecord]]) -> None:
        self.chunks_by_document = chunks_by_document
        self.calls: list[UUID] = []

    async def get_by_scraping_result_id(
        self, scraping_result_id: UUID
    ) -> IngestedDocumentSummary | None:
        return None

    async def list_chunks_by_document_id(
        self, document_id: UUID
    ) -> list[ChunkRecord]:
        self.calls.append(document_id)
        return self.chunks_by_document.get(document_id, [])


class FakeReranker(Reranker):
    """Inverte a ordem recebida, so para o teste conseguir distinguir
    'reordenado pelo reranker' de 'ordem da fusao RRF'."""

    def __init__(self) -> None:
        self.received_query: str | None = None
        self.received_top_n: int | None = None

    async def rerank(
        self,
        query: str,
        evidences: list[EvidenceChunkView],
        *,
        top_n: int,
    ) -> list[EvidenceChunkView]:
        self.received_query = query
        self.received_top_n = top_n
        return list(reversed(evidences))[:top_n]


class FakeSupplementalEvidenceProvider(SupplementalEvidenceProvider):
    def __init__(self, results: list[EvidenceChunkView]) -> None:
        self.results = results
        self.queries: list[str] = []
        self.source_types: list[str | None] = []
        self.limits: list[int] = []

    async def find(
        self,
        query: str,
        *,
        source_type: str | None = None,
        limit: int,
    ) -> list[EvidenceChunkView]:
        self.queries.append(query)
        self.source_types.append(source_type)
        self.limits.append(limit)
        return self.results[:limit]


def _make_use_case(
    *,
    vector_results: list[ChunkSearchResult],
    chunks_by_document: dict[UUID, list[ChunkRecord]],
    lexical_results: list[LexicalSearchResult] | None = None,
    reranker: Reranker | None = None,
    supplemental_evidence_provider: SupplementalEvidenceProvider | None = None,
):
    embedding_generator = FakeEmbeddingGenerator()
    vector_repository = FakeVectorRepository(vector_results)
    lexical_repository = FakeLexicalSearchRepository(lexical_results)
    reader = FakeIngestedDocumentReader(chunks_by_document)
    use_case = SearchEvidence(
        embedding_generator=embedding_generator,
        vector_repository=vector_repository,
        lexical_repository=lexical_repository,
        ingested_document_reader=reader,
        reranker=reranker,
        supplemental_evidence_provider=supplemental_evidence_provider,
    )
    return use_case, embedding_generator, vector_repository, lexical_repository, reader


@pytest.mark.anyio
async def test_search_evidence_returns_chunks_with_text_and_source() -> None:
    document_id = uuid4()
    first_chunk_id = uuid4()
    second_chunk_id = uuid4()
    chunks = [
        ChunkRecord(
            id=first_chunk_id,
            document_id=document_id,
            text="A startup usa IA generativa para atendimento.",
            source_url="https://startup.example.com",
        ),
        ChunkRecord(
            id=second_chunk_id,
            document_id=document_id,
            text="A empresa menciona inferencia em producao.",
            source_url="https://startup.example.com",
        ),
    ]
    vector_results = [
        ChunkSearchResult(
            chunk_id=second_chunk_id,
            document_id=document_id,
            source_url="https://startup.example.com",
            score=0.87,
        )
    ]
    use_case, embedding_generator, vector_repository, lexical_repository, reader = (
        _make_use_case(
            vector_results=vector_results,
            chunks_by_document={document_id: chunks},
        )
    )

    view = await use_case.execute(
        SearchEvidenceInput(query="Como a startup usa IA?", limit=3)
    )

    assert view.query == "Como a startup usa IA?"
    assert len(view.results) == 1
    assert view.results[0].chunk_id == second_chunk_id
    assert view.results[0].text == (
        "A startup usa IA generativa para atendimento.\n\n"
        "A empresa menciona inferencia em producao."
    )
    assert view.results[0].score > 0
    assert embedding_generator.received_texts[0] == "Como a startup usa IA?"
    assert vector_repository.searched_vectors == [(0.1, 0.2, 0.3)]
    # pool de candidatos (max(limit*4, MIN_CANDIDATE_POOL)), nao o limit bruto
    assert vector_repository.limits == [MIN_CANDIDATE_POOL]
    assert lexical_repository.queries == ["Como a startup usa IA?"]
    assert reader.calls == [document_id]


@pytest.mark.anyio
async def test_search_evidence_passes_source_type_to_repositories() -> None:
    use_case, _, vector_repository, lexical_repository, _ = _make_use_case(
        vector_results=[],
        chunks_by_document={},
    )

    await use_case.execute(
        SearchEvidenceInput(
            query="NVIDIA NIM",
            source_type="nvidia_knowledge",
        )
    )

    assert vector_repository.source_types == ["nvidia_knowledge"]
    assert lexical_repository.source_types == ["nvidia_knowledge"]


@pytest.mark.anyio
async def test_search_evidence_reuses_document_chunks_for_multiple_results() -> None:
    document_id = uuid4()
    first_chunk_id = uuid4()
    second_chunk_id = uuid4()
    use_case, _, _, _, reader = _make_use_case(
        vector_results=[
            ChunkSearchResult(
                chunk_id=first_chunk_id,
                document_id=document_id,
                source_url="https://source.example.com",
                score=0.9,
            ),
            ChunkSearchResult(
                chunk_id=second_chunk_id,
                document_id=document_id,
                source_url="https://source.example.com",
                score=0.8,
            ),
        ],
        chunks_by_document={
            document_id: [
                ChunkRecord(
                    id=first_chunk_id,
                    document_id=document_id,
                    text="primeiro chunk relevante",
                    source_url="https://source.example.com",
                ),
                ChunkRecord(
                    id=second_chunk_id,
                    document_id=document_id,
                    text="segundo chunk relevante",
                    source_url="https://source.example.com",
                ),
            ]
        },
    )

    view = await use_case.execute(SearchEvidenceInput(query="pergunta"))

    assert len(view.results) == 2
    assert reader.calls == [document_id]


@pytest.mark.anyio
async def test_search_evidence_expands_context_with_neighbor_chunks() -> None:
    document_id = uuid4()
    previous_chunk_id = uuid4()
    matched_chunk_id = uuid4()
    next_chunk_id = uuid4()
    chunks = [
        ChunkRecord(
            id=previous_chunk_id,
            document_id=document_id,
            text="contexto anterior",
            source_url="https://source.example.com",
        ),
        ChunkRecord(
            id=matched_chunk_id,
            document_id=document_id,
            text="chunk ranqueado",
            source_url="https://source.example.com",
        ),
        ChunkRecord(
            id=next_chunk_id,
            document_id=document_id,
            text="contexto seguinte",
            source_url="https://source.example.com",
        ),
    ]
    use_case, _, _, _, _ = _make_use_case(
        vector_results=[
            ChunkSearchResult(
                chunk_id=matched_chunk_id,
                document_id=document_id,
                source_url="https://source.example.com",
                score=0.9,
            )
        ],
        chunks_by_document={document_id: chunks},
    )

    view = await use_case.execute(SearchEvidenceInput(query="pergunta", limit=1))

    assert CONTEXT_WINDOW_RADIUS == 1
    assert view.results[0].chunk_id == matched_chunk_id
    assert view.results[0].text == (
        "contexto anterior\n\nchunk ranqueado\n\ncontexto seguinte"
    )


@pytest.mark.anyio
async def test_search_evidence_prepends_supplemental_evidence() -> None:
    document_id = uuid4()
    indexed_chunk_id = uuid4()
    supplemental_chunk_id = uuid4()
    supplemental = FakeSupplementalEvidenceProvider(
        [
            EvidenceChunkView(
                chunk_id=supplemental_chunk_id,
                document_id=supplemental_chunk_id,
                source_url="https://docs.example.com/catalog",
                text="catalogo curado",
                score=1.1,
                source_type="nvidia_knowledge",
            )
        ]
    )
    use_case, _, _, _, _ = _make_use_case(
        vector_results=[
            ChunkSearchResult(
                chunk_id=indexed_chunk_id,
                document_id=document_id,
                source_url="https://source.example.com",
                score=0.9,
            )
        ],
        chunks_by_document={
            document_id: [
                ChunkRecord(
                    id=indexed_chunk_id,
                    document_id=document_id,
                    text="chunk indexado",
                    source_url="https://source.example.com",
                )
            ]
        },
        supplemental_evidence_provider=supplemental,
    )

    view = await use_case.execute(
        SearchEvidenceInput(
            query="What does NVIDIA Clara provide?",
            source_type="nvidia_knowledge",
            limit=5,
        )
    )

    assert supplemental.queries == ["What does NVIDIA Clara provide?"]
    assert supplemental.source_types == ["nvidia_knowledge"]
    assert supplemental.limits == [5]
    assert [item.chunk_id for item in view.results] == [
        supplemental_chunk_id,
        indexed_chunk_id,
    ]


@pytest.mark.anyio
async def test_search_evidence_skips_stale_vector_without_chunk() -> None:
    document_id = uuid4()
    use_case, _, _, _, _ = _make_use_case(
        vector_results=[
            ChunkSearchResult(
                chunk_id=uuid4(),
                document_id=document_id,
                source_url="https://source.example.com",
                score=0.9,
            )
        ],
        chunks_by_document={document_id: []},
    )

    view = await use_case.execute(SearchEvidenceInput(query="pergunta"))

    assert view.results == []


@pytest.mark.anyio
async def test_search_evidence_rejects_empty_query() -> None:
    use_case, _, _, _, _ = _make_use_case(vector_results=[], chunks_by_document={})

    with pytest.raises(EmptyRagQueryError):
        await use_case.execute(SearchEvidenceInput(query="   "))


@pytest.mark.anyio
async def test_search_evidence_fuses_vector_and_lexical_only_match() -> None:
    """Um chunk so encontrado pela busca lexical (nao pela vetorial) deve
    aparecer no resultado - e exatamente o ganho da busca hibrida."""

    document_id = uuid4()
    lexical_only_chunk_id = uuid4()
    use_case, _, _, _, reader = _make_use_case(
        vector_results=[],
        lexical_results=[
            LexicalSearchResult(
                chunk_id=lexical_only_chunk_id,
                document_id=document_id,
                score=0.42,
            )
        ],
        chunks_by_document={
            document_id: [
                ChunkRecord(
                    id=lexical_only_chunk_id,
                    document_id=document_id,
                    text="termo exato mencionado no texto",
                    source_url="https://source.example.com",
                ),
            ]
        },
    )

    view = await use_case.execute(SearchEvidenceInput(query="termo exato"))

    assert len(view.results) == 1
    assert view.results[0].chunk_id == lexical_only_chunk_id
    assert reader.calls == [document_id]


@pytest.mark.anyio
async def test_search_evidence_ranks_chunk_found_in_both_sources_higher() -> None:
    document_id = uuid4()
    both_chunk_id = uuid4()
    vector_only_chunk_id = uuid4()
    chunks = [
        ChunkRecord(
            id=both_chunk_id,
            document_id=document_id,
            text="aparece nos dois rankings",
            source_url="https://source.example.com",
        ),
        ChunkRecord(
            id=vector_only_chunk_id,
            document_id=document_id,
            text="so aparece no vetorial",
            source_url="https://source.example.com",
        ),
    ]
    use_case, _, _, _, _ = _make_use_case(
        vector_results=[
            ChunkSearchResult(
                chunk_id=vector_only_chunk_id,
                document_id=document_id,
                source_url="https://source.example.com",
                score=0.95,
            ),
            ChunkSearchResult(
                chunk_id=both_chunk_id,
                document_id=document_id,
                source_url="https://source.example.com",
                score=0.90,
            ),
        ],
        lexical_results=[
            LexicalSearchResult(
                chunk_id=both_chunk_id, document_id=document_id, score=0.5
            ),
        ],
        chunks_by_document={document_id: chunks},
    )

    view = await use_case.execute(SearchEvidenceInput(query="pergunta", limit=2))

    assert view.results[0].chunk_id == both_chunk_id


@pytest.mark.anyio
async def test_search_evidence_without_reranker_keeps_fused_order() -> None:
    document_id = uuid4()
    chunk_id = uuid4()
    use_case, _, _, _, _ = _make_use_case(
        vector_results=[
            ChunkSearchResult(
                chunk_id=chunk_id,
                document_id=document_id,
                source_url="https://source.example.com",
                score=0.9,
            )
        ],
        chunks_by_document={
            document_id: [
                ChunkRecord(
                    id=chunk_id,
                    document_id=document_id,
                    text="texto",
                    source_url="https://source.example.com",
                )
            ]
        },
        reranker=None,
    )

    view = await use_case.execute(SearchEvidenceInput(query="pergunta", limit=1))

    assert len(view.results) == 1


@pytest.mark.anyio
async def test_search_evidence_uses_reranker_when_configured() -> None:
    document_id = uuid4()
    first_chunk_id = uuid4()
    second_chunk_id = uuid4()
    reranker = FakeReranker()
    use_case, _, _, _, _ = _make_use_case(
        vector_results=[
            ChunkSearchResult(
                chunk_id=first_chunk_id,
                document_id=document_id,
                source_url="https://source.example.com",
                score=0.9,
            ),
            ChunkSearchResult(
                chunk_id=second_chunk_id,
                document_id=document_id,
                source_url="https://source.example.com",
                score=0.8,
            ),
        ],
        chunks_by_document={
            document_id: [
                ChunkRecord(
                    id=first_chunk_id,
                    document_id=document_id,
                    text="primeiro",
                    source_url="https://source.example.com",
                ),
                ChunkRecord(
                    id=second_chunk_id,
                    document_id=document_id,
                    text="segundo",
                    source_url="https://source.example.com",
                ),
            ]
        },
        reranker=reranker,
    )

    view = await use_case.execute(SearchEvidenceInput(query="pergunta", limit=2))

    assert reranker.received_query == "pergunta"
    assert reranker.received_top_n == 2
    # FakeReranker inverte a ordem recebida - confirma que o reranker foi
    # de fato chamado e seu resultado foi usado.
    assert [chunk.chunk_id for chunk in view.results] == [
        second_chunk_id,
        first_chunk_id,
    ]


@pytest.mark.anyio
async def test_search_evidence_passes_document_ids_to_repositories() -> None:
    """document_ids propaga para vector e lexical como filtro extra."""
    doc_id_a = uuid4()
    doc_id_b = uuid4()
    use_case, _, vector_repository, lexical_repository, _ = _make_use_case(
        vector_results=[],
        chunks_by_document={},
    )

    await use_case.execute(
        SearchEvidenceInput(
            query="inferencia em producao",
            document_ids=[doc_id_a, doc_id_b],
        )
    )

    # FakeVectorRepository nao rastreia document_ids separadamente, mas a
    # chamada nao deve falhar (o param e aceito silenciosamente).
    # FakeLexicalSearchRepository rastreia.
    assert lexical_repository.document_ids_list == [[doc_id_a, doc_id_b]]


@pytest.mark.anyio
async def test_search_evidence_empty_document_ids_returns_no_results() -> None:
    """Lista vazia de document_ids deve retornar zero resultados sem chamar os repos."""
    document_id = uuid4()
    chunk_id = uuid4()
    use_case, embedding_generator, vector_repository, lexical_repository, _ = (
        _make_use_case(
            vector_results=[
                ChunkSearchResult(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    source_url="https://source.example.com",
                    score=0.9,
                )
            ],
            chunks_by_document={
                document_id: [
                    ChunkRecord(
                        id=chunk_id,
                        document_id=document_id,
                        text="texto",
                        source_url="https://source.example.com",
                    )
                ]
            },
        )
    )

    view = await use_case.execute(
        SearchEvidenceInput(query="algo", document_ids=[])
    )

    # Repos recebem lista vazia e devolvem [] diretamente, sem executar SQL/Qdrant.
    assert view.results == []
