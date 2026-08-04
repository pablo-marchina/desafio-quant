"""Testes do reranking NeMo NIM plugável (F3.6).

Cobrem, todos offline (sem rede/servidor/GPU, sobre a espinha verde da F3.5):

1. **Contrato plugável** (`Reranker`/`get_reranker`): o default offline satisfaz o Protocol;
   o provider real é selecionável e Cohere fica reservado p/ a F7.
2. **Reordenação lexical** (`LexicalReranker`): pontua relevância consulta×trecho pelo idf local
   da janela, preserva a proveniência citável (§8), respeita `top_n`, expõe o `retrieval_score`
   (transparência) e é determinístico.
3. **Backend real degrada limpo** (`NeMoReranker`): sem credencial/dep o rerank levanta
   `RerankerUnavailable`, não trava o build.
"""

from __future__ import annotations

import pytest

from packages.rag import (
    CohereReranker,
    LexicalReranker,
    NeMoReranker,
    RerankedChunk,
    Reranker,
    RerankerUnavailable,
    build_retriever,
    get_reranker,
    rerank,
)

# --- Contrato plugável ----------------------------------------------------------------------


def test_default_reranker_is_offline_and_satisfies_protocol() -> None:
    reranker = get_reranker()
    assert isinstance(reranker, LexicalReranker)
    assert isinstance(reranker, Reranker)  # runtime_checkable Protocol
    assert reranker.name == "lexical-offline" and reranker.model


def test_prefer_nv_selects_the_nemo_backend() -> None:
    reranker = get_reranker(prefer_nv=True)
    assert isinstance(reranker, NeMoReranker)
    assert reranker.name == "nv-rerankqa"


def test_cohere_provider_selects_the_cohere_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    # F7.4: Cohere Rerank ligado — o provider 'cohere' seleciona o CohereReranker (comparativo).
    from packages.config import get_settings

    monkeypatch.setattr(get_settings(), "reranker_provider", "cohere")
    reranker = get_reranker(prefer_nv=True)
    assert isinstance(reranker, CohereReranker)
    assert reranker.name == "cohere-rerank" and reranker.model


# --- Reordenação lexical sobre a KB real ----------------------------------------------------


def test_rerank_reorders_and_keeps_provenance() -> None:
    retriever = build_retriever()
    query = "inferência de modelos em GPU NVIDIA"
    retrieved = retriever.search(query, limit=8)
    reranked = rerank(query, retrieved)
    assert reranked and len(reranked) == len(retrieved)
    # mesma população de chunks, só reordenada (nenhum trecho inventado/perdido).
    assert {r.chunk_id for r in reranked} == {r.chunk_id for r in retrieved}
    for r in reranked:
        assert isinstance(r, RerankedChunk)
        assert r.url.startswith("http") and r.tech and r.text  # proveniência citável (§8)
        assert r.payload["chunk_id"] == r.chunk_id
    # ordenado por rerank_score desc (a ordenação final que a F3.7 consome).
    scores = [r.rerank_score for r in reranked]
    assert scores == sorted(scores, reverse=True)


def test_rerank_surfaces_a_chunk_matching_distinctive_terms() -> None:
    retriever = build_retriever()
    # termo distintivo presente em poucos chunks → o idf local o premia, sobe no rerank.
    assert any("triton" in p.payload["text"].lower() for p in retriever.index.points)
    retrieved = retriever.search("Triton TensorRT NIM", limit=10)
    reranked = rerank("Triton TensorRT NIM", retrieved)
    top = reranked[0]
    assert top.rerank_score > 0
    # o melhor reordenado cobre os termos da consulta no seu texto/contexto.
    surface = (top.title + " " + top.text).lower()
    assert any(term in surface for term in ("triton", "tensorrt", "nim"))


def test_rerank_respects_top_n() -> None:
    retriever = build_retriever()
    query = "RAG com reranking e citações"
    retrieved = retriever.search(query, limit=8)
    reranked = rerank(query, retrieved, top_n=3)
    assert len(reranked) == 3
    # são os 3 de maior rerank_score, na ordem.
    full = rerank(query, retrieved)
    assert [r.chunk_id for r in reranked] == [r.chunk_id for r in full[:3]]


def test_rerank_exposes_retrieval_score_for_transparency() -> None:
    retriever = build_retriever()
    query = "NVIDIA NIM microsserviço de inferência"
    retrieved = retriever.search(query, limit=5)
    reranked = rerank(query, retrieved)
    by_id = {r.chunk_id: r.score for r in retrieved}
    for r in reranked:
        # o score fundido (RRF) da F3.5 segue acessível ao lado do rerank_score.
        assert r.retrieval_score == by_id[r.chunk_id]


def test_rerank_is_deterministic_across_builds() -> None:
    query = "treinar e servir modelos com NeMo"
    first = rerank(query, build_retriever().search(query, limit=6))
    second = rerank(query, build_retriever().search(query, limit=6))
    assert [r.chunk_id for r in first] == [r.chunk_id for r in second]
    assert [r.rerank_score for r in first] == [r.rerank_score for r in second]


def test_rerank_on_empty_input_returns_empty() -> None:
    assert rerank("qualquer consulta", []) == ()


# --- Backend real degrada limpo offline -----------------------------------------------------


def test_nemo_reranker_degrades_cleanly_without_credentials() -> None:
    # Hook de rede/GPU: sem NVIDIA_API_KEY/NIM o rerank levanta RerankerUnavailable (offline).
    reranker = NeMoReranker(api_key="")
    retrieved = build_retriever().search("inferência GPU", limit=3)
    with pytest.raises(RerankerUnavailable):
        reranker.rerank("inferência GPU", retrieved)


def test_cohere_reranker_degrades_cleanly_without_credentials() -> None:
    # Comparativo F7.4: sem COHERE_API_KEY (ou sem o SDK) o rerank levanta RerankerUnavailable.
    reranker = CohereReranker(api_key="")
    retrieved = build_retriever().search("inferência GPU", limit=3)
    with pytest.raises(RerankerUnavailable):
        reranker.rerank("inferência GPU", retrieved)


class _FakeCohereResult:
    def __init__(self, index: int, score: float) -> None:
        self.index = index
        self.relevance_score = score


class _FakeCohereClient:
    """Client `cohere` fake (sem rede): a API devolve (índice→score) fora de ordem; testamos o
    mapeamento de volta ao RetrievedChunk + a ordenação, como o SDK real (ClientV2.rerank)."""

    def __init__(self, order: list[tuple[int, float]]) -> None:
        self._order = order

    def rerank(self, *, model: str, query: str, documents: list[str], top_n: int):  # noqa: ANN201
        ranked = [_FakeCohereResult(i, s) for i, s in self._order][:top_n]
        return type("Resp", (), {"results": ranked})()


def test_cohere_reranker_maps_results_and_orders() -> None:
    # Wiring do CohereReranker: índice→chunk + relevance_score ordenam, preservando a população.
    retrieved = build_retriever().search("Triton TensorRT NIM", limit=4)
    n = len(retrieved)
    reranker = CohereReranker(api_key="x")
    # API "devolve" os índices fora de ordem; o maior score deve subir ao topo após o _order.
    reranker._client = _FakeCohereClient([(i, (i + 1) / n) for i in range(n)])
    reranked = reranker.rerank("Triton TensorRT NIM", retrieved)
    assert len(reranked) == n
    assert {r.chunk_id for r in reranked} == {r.chunk_id for r in retrieved}  # nada inventado
    scores = [r.rerank_score for r in reranked]
    assert scores == sorted(scores, reverse=True)  # ordenado desc (contrato F3.6)
    assert reranked[0].retrieved is retrieved[n - 1]  # idx n-1 tinha o maior score
    # respeita top_n (corte no servidor + no _order).
    assert len(reranker.rerank("Triton TensorRT NIM", retrieved, top_n=2)) == 2


class _RateLimitedThenOkClient:
    """Fake do cohere: levanta 429 (TooManyRequestsError) nas primeiras `fails` chamadas e depois
    responde — exercita o retry/backoff do `CohereReranker` sob o teto da trial key (10 req/min)."""

    def __init__(self, order: list[tuple[int, float]], *, fails: int) -> None:
        self._order = order
        self._fails = fails
        self.calls = 0

    def rerank(self, *, model: str, query: str, documents: list[str], top_n: int):  # noqa: ANN201
        from cohere.errors import TooManyRequestsError

        self.calls += 1
        if self.calls <= self._fails:
            raise TooManyRequestsError(body="rate limit (trial: 10 req/min)")
        ranked = [_FakeCohereResult(i, s) for i, s in self._order][:top_n]
        return type("Resp", (), {"results": ranked})()


def test_cohere_reranker_retries_on_rate_limit(monkeypatch) -> None:
    # F7.4: a trial key é 10 req/min; o 429 não pode crashar (não é RerankerUnavailable) — espera e
    # re-tenta até responder. time.sleep mockado p/ o teste não dormir.
    monkeypatch.setattr("time.sleep", lambda _s: None)
    retrieved = build_retriever().search("Triton TensorRT NIM", limit=3)
    n = len(retrieved)
    reranker = CohereReranker(api_key="x")
    reranker._client = _RateLimitedThenOkClient([(i, (i + 1) / n) for i in range(n)], fails=2)
    reranked = reranker.rerank("Triton TensorRT NIM", retrieved)
    assert reranker._client.calls == 3  # 2× 429 + 1 sucesso
    assert {r.chunk_id for r in reranked} == {r.chunk_id for r in retrieved}  # nada inventado


def test_cohere_reranker_degrades_when_rate_limit_persists(monkeypatch) -> None:
    # 429 que não cede: esgotadas as tentativas, degrada limpo (RerankerUnavailable) p/ o lexical —
    # nunca crasha o comparativo nem inventa número. (o submódulo vem por `sys.modules`: o pacote
    # exporta a *função* `rerank`, que sombreia o atributo num `import packages.rag.rerank as rr`.)
    import sys

    rr = sys.modules["packages.rag.rerank"]
    monkeypatch.setattr("time.sleep", lambda _s: None)
    monkeypatch.setattr(rr, "_COHERE_RL_RETRIES", 3)
    retrieved = build_retriever().search("Triton TensorRT NIM", limit=3)
    reranker = CohereReranker(api_key="x")
    reranker._client = _RateLimitedThenOkClient([(0, 1.0)], fails=99)  # nunca responde
    with pytest.raises(RerankerUnavailable):
        reranker.rerank("Triton TensorRT NIM", retrieved)
    assert reranker._client.calls == 3  # tentou _COHERE_RL_RETRIES vezes, depois desistiu
