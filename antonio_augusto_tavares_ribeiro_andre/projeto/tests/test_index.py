"""Testes da indexação Qdrant dense + sparse/BM25 da KB (F3.4).

Cobrem, todos offline (sem rede/servidor/GPU):

1. **Sparse/BM25 puro e determinístico** (`BM25Encoder`): formato esparso ordenado, reproduzível
   entre instâncias, idf (termo raro discrimina mais que comum) e casamento lexical via produto
   interno consulta×documento — a base lexical que a F3.5 funde com o denso.
2. **Espinha verde** (`InMemoryVectorIndex`/`build_index`): ponto híbrido (denso + esparso) com
   payload de proveniência citável (§8), upsert idempotente por `chunk_id` e pipeline F3.1→F3.4
   reproduzível sobre a KB real.
3. **Backend real degrada limpo** (`QdrantVectorIndex`): sem `qdrant-client`/servidor levanta
   `IndexUnavailable`, não trava o build.
"""

from __future__ import annotations

import pytest

from packages.rag import (
    DEFAULT_OFFLINE_DIM,
    BM25Encoder,
    IndexedChunk,
    IndexUnavailable,
    InMemoryVectorIndex,
    QdrantVectorIndex,
    SparseVector,
    VectorIndex,
    build_index,
    embed_kb,
    get_index,
    index_chunks,
)


def _dot(a: SparseVector, b: SparseVector) -> float:
    """Produto interno esparso consulta×documento = score BM25 (como o Qdrant casa esparso)."""
    bv = dict(zip(b.indices, b.values, strict=True))
    return sum(value * bv.get(idx, 0.0) for idx, value in zip(a.indices, a.values, strict=True))


# --- Sparse/BM25 puro e determinístico -------------------------------------------------------


def test_sparse_vector_format_is_sorted_and_aligned() -> None:
    enc = BM25Encoder().fit(["nvidia nim serve modelos em gpu", "qdrant indexa vetores"])
    sparse = enc.encode_document("nvidia nim em gpu")
    assert isinstance(sparse, SparseVector)
    assert len(sparse.indices) == len(sparse.values) == sparse.nnz
    assert list(sparse.indices) == sorted(sparse.indices)  # crescente (contrato do Qdrant)
    assert len(set(sparse.indices)) == sparse.nnz  # sem índices repetidos


def test_bm25_is_deterministic_across_instances() -> None:
    corpus = ["inferência de llm em gpu nvidia", "busca híbrida com qdrant e bm25"]
    a = BM25Encoder().fit(corpus).encode_document(corpus[0])
    b = BM25Encoder().fit(corpus).encode_document(corpus[0])
    assert a == b  # reproduzível entre instâncias/processos (hashlib, não hash())


def test_bm25_idf_makes_rare_term_discriminate_more() -> None:
    # "common" em todos os docs (idf baixo) × "rare" em um só (idf alto).
    docs = ["common rare", "common", "common", "common"]
    enc = BM25Encoder().fit(docs)
    target = enc.encode_document(docs[0])
    score_rare = _dot(enc.encode_query("rare"), target)
    score_common = _dot(enc.encode_query("common"), target)
    assert score_rare > score_common > 0  # termo raro pesa mais no casamento


def test_bm25_query_matches_only_lexically_overlapping_docs() -> None:
    docs = ["common rare", "common"]
    enc = BM25Encoder().fit(docs)
    query = enc.encode_query("rare")
    assert _dot(query, enc.encode_document(docs[0])) > 0  # contém "rare"
    assert _dot(query, enc.encode_document(docs[1])) == 0  # não contém


def test_bm25_query_is_binary_over_known_vocabulary() -> None:
    enc = BM25Encoder().fit(["nvidia gpu"])
    query = enc.encode_query("nvidia desconhecido")
    assert set(query.values) == {1.0}  # peso binário por termo conhecido
    assert query.nnz == 1  # "desconhecido" fora da coorte não entra


def test_empty_text_yields_empty_sparse_vector() -> None:
    enc = BM25Encoder().fit(["algum texto"])
    assert enc.encode_document("").nnz == 0
    assert enc.encode_query("   ").nnz == 0


# --- Índice in-memory (espinha verde) --------------------------------------------------------


def test_get_index_defaults_to_in_memory_spine() -> None:
    # index_use_qdrant é off por default => espinha verde offline (sem servidor).
    assert isinstance(get_index(), InMemoryVectorIndex)
    assert isinstance(get_index(prefer_qdrant=True), QdrantVectorIndex)


def test_in_memory_index_satisfies_protocol() -> None:
    assert isinstance(InMemoryVectorIndex(), VectorIndex)


def test_in_memory_upsert_is_idempotent_by_chunk_id() -> None:
    _, encoder = build_index()  # encoder ajustado p/ reusar
    embedded = embed_kb()[:5]
    points = tuple(
        IndexedChunk(embedded=e, sparse=encoder.encode_document(e.chunk.contextual_text))
        for e in embedded
    )
    index = InMemoryVectorIndex()
    assert index.upsert(points) == len(points)
    index.upsert(points)  # re-indexar os mesmos chunks não duplica (dedup por chunk_id)
    assert index.count() == len(points)


# --- Pipeline F3.1→F3.4 sobre a KB real ------------------------------------------------------


def test_build_index_indexes_whole_kb_with_hybrid_points() -> None:
    index, encoder = build_index()
    assert isinstance(index, InMemoryVectorIndex)
    assert index.count() == len(embed_kb())  # um ponto por chunk da KB
    for point in index.points:
        assert point.dense and len(point.dense) == DEFAULT_OFFLINE_DIM  # vetor denso (F3.3)
        assert point.sparse.nnz > 0  # vetor esparso BM25 (F3.4) — ponto é híbrido
        # payload auto-suficiente p/ citar (§8):
        assert point.payload["url"].startswith("http")
        assert point.payload["tech"] and point.payload["text"]
        assert point.payload["chunk_id"] == point.chunk_id


def test_build_index_is_deterministic_across_runs() -> None:
    first, _ = build_index()
    second, _ = build_index()
    assert [p.chunk_id for p in first.points] == [p.chunk_id for p in second.points]


def test_index_chunks_returns_fitted_encoder_for_retrieval() -> None:
    embedded = embed_kb()
    index, encoder = index_chunks(embedded)
    # o encoder devolvido recupera: a consulta de uma tech casa um chunk dessa tech (lexical).
    target = next(p for p in index.points if "nim" in p.payload["text"].lower())
    query = encoder.encode_query(target.payload["tech"])
    assert _dot(query, target.sparse) > 0


# --- Backend real degrada limpo offline ------------------------------------------------------


def test_qdrant_index_degrades_cleanly_without_server() -> None:
    # Hook de rede: sem qdrant-client/servidor, qualquer operação levanta IndexUnavailable.
    with pytest.raises(IndexUnavailable):
        build_index(index=QdrantVectorIndex())
    with pytest.raises(IndexUnavailable):
        QdrantVectorIndex().count()


def test_qdrant_index_uses_configured_collection() -> None:
    from packages.config import get_settings

    assert QdrantVectorIndex().collection == get_settings().qdrant_collection
    assert QdrantVectorIndex(collection="outra").collection == "outra"
