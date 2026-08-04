"""Testes da busca híbrida dense + lexical com fusão RRF (F3.5).

Cobrem, todos offline (sem rede/servidor/GPU, sobre a espinha verde da F3.4):

1. **Fusão RRF** (`_rrf_scores`): item presente nas duas listas (denso E lexical) acumula peso e
   sobe — sem comparar scores de escalas incomparáveis (cosseno × BM25).
2. **Recuperação sobre a KB real** (`build_retriever`/`hybrid_search`): resultado fundido com
   proveniência citável (§8), casamento por tech, casamento lexical exato, limite e determinismo.
3. **Backend real degrada limpo** (`QdrantVectorIndex`): sem `qdrant-client`/servidor a busca
   levanta `IndexUnavailable`, não trava o build.
"""

from __future__ import annotations

import pytest

from packages.rag import (
    BM25Encoder,
    HybridRetriever,
    IndexUnavailable,
    QdrantVectorIndex,
    RetrievedChunk,
    build_retriever,
    hybrid_search,
)
from packages.rag.retrieve import _rrf_scores

# --- Fusão RRF ------------------------------------------------------------------------------


def test_rrf_rewards_items_present_in_both_rankings() -> None:
    dense = ["a", "b", "c"]
    sparse = ["c", "d", "a"]
    scores = _rrf_scores([dense, sparse], k=60)
    assert set(scores) == {"a", "b", "c", "d"}  # união das duas listas
    assert scores["a"] > scores["b"]  # "a" está nas duas, "b" só no denso
    assert scores["c"] > scores["d"]  # "c" nas duas, "d" só no esparso


def test_rrf_respects_rank_order_within_a_list() -> None:
    scores = _rrf_scores([["first", "second", "third"]], k=60)
    assert scores["first"] > scores["second"] > scores["third"]


# --- Recuperação sobre a KB real ------------------------------------------------------------


def test_build_retriever_returns_ready_hybrid_retriever() -> None:
    retriever = build_retriever()
    assert isinstance(retriever, HybridRetriever)
    assert retriever.index.count() > 0  # KB indexada (F3.1→F3.4)
    # embedder do índice == embedder da consulta (vetores comparáveis):
    assert retriever.embedder.model == retriever.index.points[0].embedded.model


def test_hybrid_search_returns_provenance_for_citation() -> None:
    retriever = build_retriever()
    results = retriever.search("inferência de modelos em GPU NVIDIA", limit=5)
    assert results and len(results) <= 5
    for r in results:
        assert isinstance(r, RetrievedChunk)
        assert r.score > 0  # score fundido (RRF) ordena
        assert r.url.startswith("http") and r.tech and r.text  # payload citável (§8)
        assert r.payload["chunk_id"] == r.chunk_id


def test_hybrid_search_retrieves_chunks_of_the_queried_tech() -> None:
    retriever = build_retriever()
    # consulta pelo nome de uma tech da KB → trechos dessa tech devem ser recuperados.
    target_tech = retriever.index.points[0].payload["tech"]
    results = retriever.search(target_tech, limit=8)
    assert any(r.tech == target_tech for r in results)


def test_lexical_match_surfaces_exact_term() -> None:
    retriever = build_retriever()
    # termo distintivo presente num chunk → o lado BM25 da fusão o traz com texto contendo o termo.
    point = next(p for p in retriever.index.points if "triton" in p.payload["text"].lower())
    results = retriever.search("triton", limit=10)
    assert any("triton" in r.text.lower() for r in results)
    # transparência da fusão: na espinha verde os scores componentes ficam expostos.
    assert any(r.sparse_score is not None and r.sparse_score > 0 for r in results)
    assert point  # garantia de que o termo existe na KB (senão o teste seria vacuamente verde)


def test_hybrid_search_respects_limit_and_is_ordered_by_score() -> None:
    retriever = build_retriever()
    results = retriever.search("Triton TensorRT NIM", limit=3)
    assert len(results) <= 3
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)  # ordenado por score fundido desc


def test_hybrid_search_is_deterministic_across_builds() -> None:
    first = build_retriever().search("RAG com reranking e citações", limit=5)
    second = build_retriever().search("RAG com reranking e citações", limit=5)
    assert [r.chunk_id for r in first] == [r.chunk_id for r in second]


def test_hybrid_search_rejects_unsupported_index() -> None:
    class _NotAnIndex:
        pass

    with pytest.raises(TypeError):
        hybrid_search(
            "x", index=_NotAnIndex(), encoder=BM25Encoder().fit(["algum texto"])
        )


# --- Backend real degrada limpo offline -----------------------------------------------------


def test_qdrant_search_degrades_cleanly_without_server() -> None:
    # Hook de rede: sem qdrant-client/servidor a busca levanta IndexUnavailable (degrada offline).
    encoder = BM25Encoder().fit(["nvidia nim gpu", "qdrant busca híbrida"])
    with pytest.raises(IndexUnavailable):
        hybrid_search("nvidia", index=QdrantVectorIndex(), encoder=encoder)
