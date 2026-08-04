"""Infra de RAG: Qdrant (modo local) + chunking + embeddings + busca híbrida + Cohere rerank.

Compartilhada por app/ingest.py (offline) e app/nvidia_rag.py (online). A busca é
híbrida: vetor denso (semântica) + esparso BM25 (termos exatos, siglas) fundidos
por RRF; o Cohere Rerank reordena os melhores (top-5).

Embeddings densos são provider-agnósticos: Gemini ou fastembed local
(grátis), via `settings.embedding_provider`.
"""

import atexit
import re
import time

import cohere
from fastembed import SparseTextEmbedding, TextEmbedding
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient, models

from app.config import settings

_DENSE_LOCAL_MODEL = "BAAI/bge-small-en-v1.5"

# carregados só no primeiro uso
_client: QdrantClient | None = None
_sparse: SparseTextEmbedding | None = None
_dense_local: TextEmbedding | None = None
_dense_gemini = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        # servidor (Docker) se QDRANT_URL estiver setado; senão, modo local embarcado
        _client = (
            QdrantClient(url=settings.qdrant_url)
            if settings.qdrant_url
            else QdrantClient(path=settings.qdrant_path)
        )
    return _client


@atexit.register
def _fechar_client() -> None:
    """Fecha o Qdrant local no fim do processo — evita o aviso ruidoso do __del__
    durante o shutdown do interpretador."""
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None


# ---------- embeddings ----------
def embed_dense(textos: list[str]) -> list[list[float]]:
    if settings.embedding_provider == "local":
        global _dense_local
        if _dense_local is None:
            _dense_local = TextEmbedding(_DENSE_LOCAL_MODEL)
        return [v.tolist() for v in _dense_local.embed(textos)]
    if settings.embedding_provider == "gemini":
        global _dense_gemini
        if _dense_gemini is None:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            _dense_gemini = GoogleGenerativeAIEmbeddings(
                model=settings.gemini_embedding_model, google_api_key=settings.gemini_api_key
            )
        return _dense_gemini.embed_documents(textos)
    emb = OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key)
    return emb.embed_documents(textos)


def _embed_sparse(textos: list[str]):
    global _sparse
    if _sparse is None:
        _sparse = SparseTextEmbedding("Qdrant/bm25")
    return list(_sparse.embed(textos))


def _sparse_vec(sv) -> models.SparseVector:
    return models.SparseVector(indices=sv.indices.tolist(), values=sv.values.tolist())


def _dense_dim() -> int:
    return len(embed_dense(["probe"])[0])


# ---------- limpeza de corpus ----------
_RE_DATA = re.compile(r"^\[?\s*\d{1,4}[/.\-]\d{1,2}")  # linhas tipo "[2024/11/09] ..."


def limpar(texto: str) -> str:
    """Descarta ruído de README do GitHub: changelog/datas, badges e linhas
    majoritariamente não-textuais (emoji/símbolos). Mantém o texto técnico."""
    linhas = []
    for ln in texto.split("\n"):
        s = ln.strip()
        if not s:
            continue
        if _RE_DATA.match(s):
            continue
        letras = sum(c.isalpha() for c in s)
        if letras / len(s) < 0.5:  # badge/emoji/símbolo
            continue
        linhas.append(s)
    return "\n".join(linhas)


# ---------- chunking (por parágrafo, com overlap) ----------
def chunk_texto(texto: str, fonte: str, titulo: str = "", tamanho: int = 800, overlap: int = 100) -> list[dict]:
    paras = [p.strip() for p in texto.split("\n") if p.strip()]
    chunks: list[str] = []
    atual = ""
    for p in paras:
        if atual and len(atual) + len(p) + 1 > tamanho:
            chunks.append(atual)
            cauda = atual[-overlap:] if overlap else ""
            atual = (cauda + " " + p).strip()
        else:
            atual = (atual + " " + p).strip() if atual else p
    if atual:
        chunks.append(atual)
    return [{"texto": c, "fonte": fonte, "titulo": titulo} for c in chunks]


# ---------- coleção / ingestão ----------
def ensure_collection(recriar: bool = False) -> None:
    client = get_client()
    nome = settings.qdrant_collection
    if recriar and client.collection_exists(nome):
        client.delete_collection(nome)
    if not client.collection_exists(nome):
        client.create_collection(
            nome,
            vectors_config={"dense": models.VectorParams(size=_dense_dim(), distance=models.Distance.COSINE)},
            sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )


def indexar(docs: list[dict], batch: int = 95) -> int:
    """docs: [{texto, fonte, titulo}]. Embeda (denso+esparso) e faz upsert no Qdrant.

    Embeda em lotes; com provider=gemini, pausa entre lotes para respeitar o tier
    grátis (100 embeddings/min).
    """
    if not docs:
        return 0
    throttle = settings.embedding_provider == "gemini"
    pontos: list[models.PointStruct] = []
    for i in range(0, len(docs), batch):
        lote = docs[i : i + batch]
        textos = [d["texto"] for d in lote]
        densos = embed_dense(textos)
        esparsos = _embed_sparse(textos)
        for j, (d, dv, sv) in enumerate(zip(lote, densos, esparsos)):
            pontos.append(
                models.PointStruct(id=i + j, vector={"dense": dv, "bm25": _sparse_vec(sv)}, payload=d)
            )
        if throttle and i + batch < len(docs):
            time.sleep(61)
    get_client().upsert(settings.qdrant_collection, pontos)
    return len(pontos)


# ---------- recuperação online (2 estágios) ----------
def buscar_hibrido(query: str, k: int | None = None) -> list[dict]:
    """Estágio 1 (recall): denso + esparso fundidos por RRF → k candidatos."""
    k = k or settings.rag_top_k
    qd = embed_dense([query])[0]
    qs = _sparse_vec(_embed_sparse([query])[0])
    res = get_client().query_points(
        settings.qdrant_collection,
        prefetch=[
            models.Prefetch(query=qd, using="dense", limit=k),
            models.Prefetch(query=qs, using="bm25", limit=k),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=k,
        with_payload=True,
    )
    return [p.payload for p in res.points]


def rerankear(query: str, candidatos: list[dict], n: int | None = None) -> list[dict]:
    """Estágio 2 (precisão): Cohere Rerank (cross-encoder) → top-n.

    Resiliente ao rate-limit da Cohere (trial = 10/min): tenta de novo com backoff
    e, se ainda assim falhar, retorna os candidatos sem rerank — perde precisão,
    mas não derruba o pipeline.
    """
    n = n or settings.rag_top_n
    if not candidatos:
        return []
    co = cohere.Client(api_key=settings.cohere_api_key)
    for tentativa in range(3):
        try:
            res = co.rerank(
                model=settings.cohere_rerank_model,
                query=query,
                documents=[c["texto"] for c in candidatos],
                top_n=min(n, len(candidatos)),
            )
            return [candidatos[r.index] for r in res.results]
        except cohere.TooManyRequestsError:
            if tentativa < 2:
                time.sleep(8 * (tentativa + 1))  # limite é por minuto; espera e repete
                continue
            print("[rerank] Cohere 429 — degradando p/ candidatos sem rerank.")
    return candidatos[:n]


def recuperar(query: str) -> list[dict]:
    """Caminho online completo: busca híbrida → rerank → top-n trechos com fonte."""
    return rerankear(query, buscar_hibrido(query))
