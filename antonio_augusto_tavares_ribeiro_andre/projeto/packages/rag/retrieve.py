"""Busca híbrida na KB — dense (nv-embedqa) + lexical (BM25) com fusão RRF (F3.5).

Quinta etapa do pipeline RAG (ARQUITETURA §4): consulta o índice híbrido (F3.4) combinando
o sinal **denso** (semântica, nv-embedqa/F3.3) com o **lexical/BM25** (casamento de termos) e
**funde os dois rankings** num só, devolvendo os trechos mais relevantes **com a proveniência
para citar** (§8). É a base que o reranker (F3.6) reordena e o nó `nvidia_rag` (F3.7) responde.

Decisões (F3.5), honrando o que já está travado no projeto:

- **Fusão por Reciprocal Rank Fusion (RRF)** — junta os dois rankings pela *posição*, não pelo
  score bruto: o cosseno denso (∈[-1,1]) e o BM25 (ilimitado) vivem em escalas incomparáveis, e
  o RRF é robusto a isso (cada lista contribui `1/(k+rank)`). É o **mesmo método default do
  Qdrant** para busca híbrida, então a espinha verde offline e o backend Qdrant fundem do mesmo
  jeito (paridade de semântica entre os dois caminhos).
- **A busca segue o índice que recebe** (peça plugável, decisão travada desde a F3.1): sobre o
  `InMemoryVectorIndex` (default/espinha) a fusão roda em Python lendo `index.points` (a
  superfície de leitura que a F3.4 já anunciava); sobre o `QdrantVectorIndex` (dogfood) usa a
  **Query API nativa** (prefetch denso + esparso → `FusionQuery(RRF)`), fundindo no servidor.
- **Backend real degrada limpo** — o caminho Qdrant reusa o `_ensure_client` da F3.4, que levanta
  `IndexUnavailable` sem `qdrant-client`/servidor; offline a busca cai para o in-memory. O build/CI
  nunca trava na rede (como `NVEmbedQA`/F3.3 e `RivaTranscriber`/F3.1b).
- **Consulta com o MESMO embedder do índice** — `embed_query` é assimétrico no nv-embedqa
  (`input_type=query`); o `HybridRetriever` carrega o embedder que construiu o índice para o vetor
  da consulta ser comparável ao dos pontos (offline o `HashingEmbedder` é determinístico/stateless,
  então reconstruí-lo dá o mesmo vetor).
- **Resultado auto-suficiente p/ citar** (§8): `RetrievedChunk` carrega o `payload` herdado do
  chunk (tech/url/seção/texto/hash + modelo do vetor) — a F3.7 cita direto do resultado, sem
  reabrir o índice. `dense_score`/`sparse_score` ficam expostos (transparência da fusão).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from .embed import Embedder, embed_kb, get_embedder
from .index import (
    DENSE_VECTOR,
    SPARSE_VECTOR,
    BM25Encoder,
    InMemoryVectorIndex,
    QdrantVectorIndex,
    SparseVector,
    VectorIndex,
    build_index,
)

# Quantos trechos a busca devolve por default (entra no rerank/F3.6 antes da resposta/F3.7).
DEFAULT_LIMIT = 5

# Janela de candidatos puxada de CADA lista (denso/esparso) antes de fundir — maior que o limite
# final p/ a fusão ter material dos dois lados sem custar a coorte inteira.
DEFAULT_PREFETCH = 20

# Constante do RRF (Cormack et al.): amortece o peso das primeiras posições. 60 é o valor
# clássico e o default do Qdrant — manter casa a espinha verde com o backend de produção.
RRF_K = 60


class RetrievedChunk(BaseModel):
    """Trecho recuperado pela busca híbrida (F3.5) — fundido e pronto p/ citar (§8).

    `score` é o valor fundido (RRF) que ordena o resultado; `payload` é a proveniência herdada do
    chunk (a F3.7 cita direto dela). `dense_score`/`sparse_score` ficam visíveis para transparência
    da fusão — são `None` no caminho Qdrant (a fusão acontece no servidor).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    score: float = Field(description="Score fundido (RRF) — ordenação final do resultado.")
    payload: dict = Field(description="Proveniência herdada do chunk p/ citar (§8).")
    dense_score: float | None = Field(default=None, description="Cosseno denso (None no Qdrant).")
    sparse_score: float | None = Field(default=None, description="BM25 lexical (None no Qdrant).")

    @property
    def text(self) -> str:
        """Texto fiel do trecho (citação, F3.7)."""
        return self.payload.get("text", "")

    @property
    def tech(self) -> str:
        return self.payload.get("tech", "")

    @property
    def url(self) -> str:
        return self.payload.get("url", "")

    @property
    def section(self) -> str:
        return self.payload.get("section", "")

    @property
    def title(self) -> str:
        return self.payload.get("title", "")

    @property
    def source_type(self) -> str:
        return self.payload.get("source_type", "")


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosseno entre dois vetores densos (0.0 se algum for nulo — caso degenerado)."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _sparse_dot(query: SparseVector, doc: SparseVector) -> float:
    """Produto interno esparso consulta×documento = score BM25 (como o Qdrant casa esparso)."""
    dv = dict(zip(doc.indices, doc.values, strict=True))
    return sum(val * dv.get(idx, 0.0) for idx, val in zip(query.indices, query.values, strict=True))


def _rrf_scores(rankings: Sequence[Sequence[str]], k: int) -> dict[str, float]:
    """Funde rankings por Reciprocal Rank Fusion: cada lista soma `1/(k+rank)` (rank 1-based).

    Item presente em mais de uma lista acumula contribuição — é o que faz a fusão premiar o que
    denso E lexical concordam, sem comparar scores de escalas diferentes.
    """
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return fused


def _rank_positive(scored: Sequence[tuple[str, float]], limit: int) -> list[str]:
    """Ordena (id, score) desc (desempate por id), mantém só score>0 e corta no top `limit`."""
    ordered = sorted(scored, key=lambda item: (-item[1], item[0]))
    return [chunk_id for chunk_id, score in ordered if score > 0.0][:limit]


def _search_in_memory(
    index: InMemoryVectorIndex,
    dense: Sequence[float],
    sparse: SparseVector,
    *,
    limit: int,
    prefetch: int,
    rrf_k: int,
) -> tuple[RetrievedChunk, ...]:
    """Busca híbrida sobre a espinha verde: cosseno denso + BM25 esparso, fundidos por RRF."""
    points = index.points
    dense_scored = [(p.chunk_id, _cosine(dense, p.dense)) for p in points]
    sparse_scored = [(p.chunk_id, _sparse_dot(sparse, p.sparse)) for p in points]
    dense_ranked = _rank_positive(dense_scored, prefetch)
    sparse_ranked = _rank_positive(sparse_scored, prefetch)
    fused = _rrf_scores([dense_ranked, sparse_ranked], rrf_k)
    by_id = {p.chunk_id: p for p in points}
    dense_map = dict(dense_scored)
    sparse_map = dict(sparse_scored)
    ordered = sorted(fused.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return tuple(
        RetrievedChunk(
            chunk_id=chunk_id,
            score=score,
            payload=by_id[chunk_id].payload,
            dense_score=dense_map.get(chunk_id),
            sparse_score=sparse_map.get(chunk_id),
        )
        for chunk_id, score in ordered
    )


def _search_qdrant(
    index: QdrantVectorIndex,
    dense: Sequence[float],
    sparse: SparseVector,
    *,
    limit: int,
    prefetch: int,
) -> tuple[RetrievedChunk, ...]:
    """Busca híbrida no Qdrant via Query API: prefetch denso + esparso → fusão RRF no servidor.

    Reusa o `_ensure_client` da F3.4 (levanta `IndexUnavailable` sem dep/servidor → degrada limpo).
    O Qdrant funde com seu RRF (k=60, casando o `RRF_K` da espinha verde); o score do ponto já é o
    fundido, então `dense_score`/`sparse_score` ficam `None` aqui.
    """
    from qdrant_client import models

    client = index._ensure_client()  # noqa: SLF001 - reuso do degrade-clean centralizado da F3.4
    response = client.query_points(
        index.collection,
        prefetch=[
            models.Prefetch(query=list(dense), using=DENSE_VECTOR, limit=prefetch),
            models.Prefetch(
                query=models.SparseVector(
                    indices=list(sparse.indices), values=list(sparse.values)
                ),
                using=SPARSE_VECTOR,
                limit=prefetch,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
        with_payload=True,
    )
    return tuple(
        RetrievedChunk(
            chunk_id=str((point.payload or {}).get("chunk_id", point.id)),
            score=float(point.score),
            payload=dict(point.payload or {}),
        )
        for point in response.points
    )


def hybrid_search(
    query: str,
    *,
    index: VectorIndex,
    encoder: BM25Encoder,
    embedder: Embedder | None = None,
    limit: int = DEFAULT_LIMIT,
    prefetch: int = DEFAULT_PREFETCH,
    rrf_k: int = RRF_K,
) -> tuple[RetrievedChunk, ...]:
    """Consulta híbrida (denso + lexical) com fusão RRF — segue o backend do `index` recebido.

    Embeda a consulta (`embed_query`, assimétrico no nv-embedqa) e a codifica em BM25 com o
    `encoder` ajustado na indexação (F3.4), depois despacha para a espinha in-memory ou o Qdrant.
    Passe o **mesmo** embedder que construiu o índice (default `get_embedder()`, que casa o caminho
    de build default).
    """
    embedder = embedder or get_embedder()
    dense = embedder.embed_query(query)
    sparse = encoder.encode_query(query)
    if isinstance(index, QdrantVectorIndex):
        return _search_qdrant(index, dense, sparse, limit=limit, prefetch=prefetch)
    if isinstance(index, InMemoryVectorIndex):
        return _search_in_memory(
            index, dense, sparse, limit=limit, prefetch=prefetch, rrf_k=rrf_k
        )
    raise TypeError(f"índice não suportado p/ busca híbrida (F3.5): {type(index).__name__}")


@dataclass(frozen=True)
class HybridRetriever:
    """Recuperador híbrido pronto p/ consultar: amarra índice + encoder BM25 + embedder (F3.5).

    Carrega o **mesmo** embedder que construiu o índice (vetor de consulta comparável aos pontos)
    e o `encoder` BM25 ajustado na coorte. `search` é a superfície que o reranker (F3.6) e o nó
    `nvidia_rag` (F3.7) chamam.
    """

    index: VectorIndex
    encoder: BM25Encoder
    embedder: Embedder

    def search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_LIMIT,
        prefetch: int = DEFAULT_PREFETCH,
        rrf_k: int = RRF_K,
    ) -> tuple[RetrievedChunk, ...]:
        return hybrid_search(
            query,
            index=self.index,
            encoder=self.encoder,
            embedder=self.embedder,
            limit=limit,
            prefetch=prefetch,
            rrf_k=rrf_k,
        )


def build_retriever(
    *,
    embedder: Embedder | None = None,
    index: VectorIndex | None = None,
    encoder: BM25Encoder | None = None,
) -> HybridRetriever:
    """Pipeline F3.1→F3.5: ingere/chunkifica/embeda/indexa a KB e devolve um `HybridRetriever`.

    Usa o **mesmo** embedder para construir o índice e para responder consultas (vetores
    comparáveis). Offline (default) é reproduzível e roda sem rede — base p/ a F3.6/F3.7.
    """
    embedder = embedder or get_embedder()
    embedded = embed_kb(embedder=embedder)
    index, encoder = build_index(embedded=embedded, index=index, encoder=encoder)
    return HybridRetriever(index=index, encoder=encoder, embedder=embedder)


__all__ = [
    "DEFAULT_LIMIT",
    "DEFAULT_PREFETCH",
    "RRF_K",
    "RetrievedChunk",
    "HybridRetriever",
    "hybrid_search",
    "build_retriever",
]
