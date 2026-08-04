"""Testes do retrieval — Qdrant EM MEMÓRIA + embeddings falsos previsíveis.

Os embeddings falsos mapeiam cada texto para um vetor "one-hot" por palavra-chave
(nim / nemo / triton). Assim a similaridade de cosseno é DETERMINÍSTICA: uma
query sobre "nim" precisa devolver o chunk do NIM em primeiro lugar. Testa-se o
ranqueamento da mecânica, não a qualidade semântica real.
"""
from qdrant_client import QdrantClient

from rag.chunk import Chunk
from rag.index import index_chunks
from rag.retrieve import format_context, retrieve

KEYWORDS = ["nim", "nemo", "triton"]


class FakeEmbeddings:
    """Vetor one-hot pela presença de cada palavra-chave no texto."""

    def _vec(self, texto: str) -> list[float]:
        t = texto.lower()
        v = [1.0 if kw in t else 0.0 for kw in KEYWORDS]
        return v if any(v) else [0.1, 0.1, 0.1]  # evita vetor nulo

    def embed_documents(self, textos: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in textos]

    def embed_query(self, texto: str) -> list[float]:
        return self._vec(texto)


CHUNKS = [
    Chunk(tech="NVIDIA NIM", url="https://x/nim", text="microsserviços NIM de inferência", chunk_index=0),
    Chunk(tech="NVIDIA NeMo", url="https://x/nemo", text="NeMo framework de LLMs", chunk_index=0),
    Chunk(tech="Triton", url="https://x/triton", text="Triton inference server", chunk_index=0),
]


def _indexed_client() -> QdrantClient:
    client = QdrantClient(":memory:")
    index_chunks(CHUNKS, client, FakeEmbeddings(), collection_name="t")
    return client


def test_retrieve_traz_o_chunk_mais_relevante_primeiro():
    client = _indexed_client()
    out = retrieve("quero usar NIM em produção", client=client,
                   embeddings=FakeEmbeddings(), collection_name="t")
    assert out[0].tech == "NVIDIA NIM"


def test_retrieve_respeita_top_k():
    client = _indexed_client()
    out = retrieve("nemo", top_k=2, client=client,
                   embeddings=FakeEmbeddings(), collection_name="t")
    assert len(out) == 2


def test_retrieve_devolve_score_e_proveniencia():
    client = _indexed_client()
    out = retrieve("triton", client=client,
                   embeddings=FakeEmbeddings(), collection_name="t")
    top = out[0]
    assert top.tech == "Triton"
    assert top.url == "https://x/triton"
    assert isinstance(top.score, float)


def test_scores_vem_em_ordem_decrescente():
    client = _indexed_client()
    out = retrieve("nim", top_k=3, client=client,
                   embeddings=FakeEmbeddings(), collection_name="t")
    scores = [c.score for c in out]
    assert scores == sorted(scores, reverse=True)


def test_format_context_inclui_citacao():
    client = _indexed_client()
    out = retrieve("nim", top_k=1, client=client,
                   embeddings=FakeEmbeddings(), collection_name="t")
    contexto = format_context(out)
    assert "[NVIDIA NIM](https://x/nim)" in contexto
    assert "microsserviços NIM" in contexto
