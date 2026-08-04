"""Testes da indexação — Qdrant EM MEMÓRIA + embeddings falsos.

`QdrantClient(":memory:")` roda o Qdrant embutido no processo (sem container,
sem rede). Os embeddings são falsos e determinísticos — o que se testa aqui é a
MECÂNICA de indexar (criar coleção, upsert, payload), não a qualidade vetorial.
"""
import json

from qdrant_client import QdrantClient

from rag.chunk import Chunk
from rag.index import build_index, index_chunks, load_corpus


class FakeEmbeddings:
    """Imita a interface mínima do LangChain: embed_documents -> vetores.

    Vetor trivial e determinístico por texto (comprimento + nº de palavras);
    suficiente para validar a indexação sem chamar a OpenAI.
    """

    def embed_documents(self, textos: list[str]) -> list[list[float]]:
        return [[float(len(t)), float(len(t.split())), 1.0] for t in textos]


def _client() -> QdrantClient:
    return QdrantClient(":memory:")


CHUNKS = [
    Chunk(tech="NVIDIA NIM", url="https://x/nim", text="microsserviços de inferência", chunk_index=0),
    Chunk(tech="NVIDIA NeMo", url="https://x/nemo", text="framework de LLMs", chunk_index=0),
]


def test_index_chunks_cria_colecao_e_grava_pontos():
    client = _client()
    n = index_chunks(CHUNKS, client, FakeEmbeddings(), collection_name="t")

    assert n == 2
    assert client.collection_exists("t")
    assert client.count("t").count == 2


def test_index_preserva_payload_de_proveniencia():
    client = _client()
    index_chunks(CHUNKS, client, FakeEmbeddings(), collection_name="t")

    pontos, _ = client.scroll("t", with_payload=True, limit=10)
    techs = {p.payload["tech"] for p in pontos}
    assert techs == {"NVIDIA NIM", "NVIDIA NeMo"}
    assert all({"tech", "url", "text", "chunk_index"} <= p.payload.keys() for p in pontos)


def test_reindexar_nao_duplica_pontos():
    client = _client()
    index_chunks(CHUNKS, client, FakeEmbeddings(), collection_name="t")
    index_chunks(CHUNKS, client, FakeEmbeddings(), collection_name="t")  # de novo
    assert client.count("t").count == 2  # recriou, não somou


def test_index_chunks_vazio_retorna_zero():
    assert index_chunks([], _client(), FakeEmbeddings(), collection_name="t") == 0


def test_build_index_le_corpus_do_disco(tmp_path):
    corpus = tmp_path / "c.jsonl"
    registros = [
        {"tech": "NVIDIA NIM", "url": "https://x/nim", "text": "um texto curto sobre NIM"},
        {"tech": "NVIDIA NeMo", "url": "https://x/nemo", "text": "um texto curto sobre NeMo"},
    ]
    corpus.write_text("\n".join(json.dumps(r) for r in registros), encoding="utf-8")

    # confirma que load_corpus reconstrói os docs
    docs = load_corpus(corpus)
    assert [d.tech for d in docs] == ["NVIDIA NIM", "NVIDIA NeMo"]

    client = _client()
    n = build_index(corpus_path=corpus, client=client, embeddings=FakeEmbeddings(), collection_name="t")
    assert n == 2
    assert client.count("t").count == 2
