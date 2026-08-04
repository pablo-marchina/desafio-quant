"""Testes do reranking — Cohere FALSO e determinístico, sem rede.

O fake imita a resposta do Cohere V2: ordena os documentos pela contagem de
ocorrências da palavra-chave da query e devolve objetos com `.index` e
`.relevance_score`. Testa-se a MECÂNICA (reordenar, cortar em top_n, preservar
proveniência e os dois scores), não a qualidade real do modelo.
"""
from types import SimpleNamespace

import pytest
from qdrant_client import QdrantClient

from rag.chunk import Chunk
from rag.index import index_chunks
from rag.rerank import _fallback_sem_rerank, rerank, retrieve_and_rerank
from rag.retrieve import RetrievedChunk


class FakeCohere:
    """Imita ClientV2.rerank: relevância = nº de vezes que a query aparece no doc."""

    def rerank(self, *, model, query, documents, top_n):
        pontuados = [
            (i, float(doc.lower().count(query.lower())))
            for i, doc in enumerate(documents)
        ]
        pontuados.sort(key=lambda t: t[1], reverse=True)
        results = [
            SimpleNamespace(index=i, relevance_score=score)
            for i, score in pontuados[:top_n]
        ]
        return SimpleNamespace(results=results)


def _chunk(tech, text, score):
    return RetrievedChunk(tech=tech, url=f"https://x/{tech}", text=text,
                          chunk_index=0, score=score)


# Ordem de entrada NÃO é a ideal: o mais relevante a "triton" está por último,
# com o pior score vetorial — o rerank precisa promovê-lo.
CHUNKS = [
    _chunk("nim", "texto sobre nim e inferência", 0.90),
    _chunk("nemo", "texto sobre nemo framework", 0.80),
    _chunk("triton", "triton triton triton serve modelos", 0.40),
]


def test_rerank_promove_o_mais_relevante():
    out = rerank("triton", CHUNKS, top_n=3, client=FakeCohere())
    assert out[0].tech == "triton"          # subiu do último para o primeiro
    assert out[0].vector_score == 0.40      # apesar do pior score vetorial


def test_rerank_corta_em_top_n():
    out = rerank("triton", CHUNKS, top_n=1, client=FakeCohere())
    assert len(out) == 1


def test_rerank_guarda_os_dois_scores():
    out = rerank("nim", CHUNKS, top_n=1, client=FakeCohere())
    top = out[0]
    assert top.vector_score == 0.90         # score vetorial original preservado
    assert top.rerank_score == 1.0          # "nim" aparece 1x no doc do nim
    assert top.tech == "nim"


def test_rerank_preserva_proveniencia():
    out = rerank("nemo", CHUNKS, top_n=3, client=FakeCohere())
    assert all(c.url == f"https://x/{c.tech}" for c in out)


def test_rerank_lista_vazia_nao_chama_cohere():
    # se chamasse o cliente, o None quebraria — então tem de retornar [] antes
    assert rerank("qualquer", [], client=None) == []


def test_rerank_top_n_maior_que_candidatos():
    out = rerank("triton", CHUNKS, top_n=99, client=FakeCohere())
    assert len(out) == 3  # não estoura: limita ao número de documentos


def test_rerank_falha_sem_chave(monkeypatch):
    # sem client injetado e sem COHERE_API_KEY -> erro explícito
    from core.config import settings
    monkeypatch.setattr(settings, "cohere_api_key", "")
    with pytest.raises(RuntimeError, match="COHERE_API_KEY"):
        rerank("x", CHUNKS, client=None)


# --- degradação graciosa (rate limit / falha do Cohere) -------------------

def test_fallback_sem_rerank_ordena_por_score_vetorial():
    candidatos = [
        _chunk("A", "txt a", 0.30), _chunk("B", "txt b", 0.90), _chunk("C", "txt c", 0.50),
    ]
    out = _fallback_sem_rerank(candidatos, top_n=2)
    assert [c.tech for c in out] == ["B", "C"]      # top 2 por score vetorial
    # sem rerank: o rerank_score vira o próprio score vetorial (proxy)
    assert out[0].rerank_score == 0.90
    assert out[0].vector_score == 0.90


class _FakeEmbeddings:
    def embed_documents(self, textos):
        return [[float(len(t)), 1.0] for t in textos]

    def embed_query(self, texto):
        return [float(len(texto)), 1.0]


class _CohereQueCai:
    def rerank(self, **kwargs):
        raise RuntimeError("429 Too Many Requests")


def test_retrieve_and_rerank_degrada_quando_cohere_falha():
    client = QdrantClient(":memory:")
    chunks = [
        Chunk(tech="NIM", url="https://x/nim", text="inferência", chunk_index=0),
        Chunk(tech="NeMo", url="https://x/nemo", text="framework de LLMs", chunk_index=0),
    ]
    index_chunks(chunks, client, _FakeEmbeddings(), collection_name="t")

    # Cohere indisponível (429) -> NÃO propaga erro: cai no retrieval vetorial.
    out = retrieve_and_rerank(
        "qualquer", fetch_k=5, top_n=2,
        qdrant_client=client, embeddings=_FakeEmbeddings(),
        cohere_client=_CohereQueCai(), collection_name="t",
    )
    assert len(out) >= 1
    assert all(c.rerank_score == c.vector_score for c in out)  # marca da degradação
