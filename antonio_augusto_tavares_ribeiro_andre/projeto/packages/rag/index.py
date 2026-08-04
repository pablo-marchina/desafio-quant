"""Indexação da KB no Qdrant — dense (nv-embedqa) + sparse/BM25 (F3.4).

Quarta etapa do pipeline RAG (ARQUITETURA §4): pega os `EmbeddedChunk` densos (F3.3) e os
indexa num índice **híbrido** — vetor **denso** (nv-embedqa, F3.3) para semelhança semântica
**+** vetor **esparso/BM25** para casamento lexical — pronto para a busca híbrida com fusão de
scores (F3.5) e a recuperação com citações (F3.7). O backend **preferido** (dogfood) é o
**Qdrant** (coleção com vetor nomeado denso + esparso); a espinha verde é um índice in-memory.

Decisões (F3.4), honrando o que já está travado no projeto:

- **Sparse/BM25 puro e determinístico** (`BM25Encoder`) — mesma filosofia do `HashingEmbedder`
  (F3.3): sem rede/GPU/dep externa (não usa `rank-bm25`), **reproduzível entre processos** (id
  de termo via `hashlib`, não o `hash()` randômico). Ajusta-se à coorte de docs (`fit`: df→idf +
  comprimento médio) e gera o **vetor esparso BM25** do documento (saturação de tf + normalização
  por tamanho) e o vetor binário da consulta — o produto interno reconstrói o score BM25, que é
  como o Qdrant casa esparso×esparso. Assim a F3.5 roda/testa o lexical offline.
- **Backend real é hook de rede que degrada limpo** — como o `NVEmbedQA` (F3.3) e o
  `RivaTranscriber` (F3.1b): `QdrantVectorIndex` exige `qdrant-client` + servidor em `qdrant_url`
  e levanta `IndexUnavailable` quando a infra falta; o build/CI nunca trava na rede.
- **Espinha verde offline e determinística** (travada desde a F3.1): o default é o
  `InMemoryVectorIndex` — guarda os pontos em memória (upsert idempotente por `chunk_id` = dedup,
  como o `content_sha256` no nível do chunk) para a F3.5 buscar sem subir o Qdrant. Troca-se pelo
  Qdrant via config (`index_use_qdrant`) ou injeção, sem mexer no resto do pipeline (peça plugável).
- **Coleção separada da coorte** (`KB_COLLECTION`): a KB NVIDIA (F3.1) e o Cohort-RAG sobre a
  tabela `company` (F3.10) compartilham embedder/Qdrant/reranker, mas vivem em coleções distintas.
- **Ponto auto-suficiente p/ citar** (§8): o payload carrega a proveniência herdada do chunk
  (`url`/`tech`/`section`/`text`/`content_sha256`) + o `model` do vetor — nenhuma recuperação sem
  fonte rastreável; a F3.7 cita direto do payload recuperado.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
import uuid
from collections import Counter
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from packages.config import get_settings

from .embed import EmbeddedChunk, embed_kb

# Coleção da KB NVIDIA no Qdrant. A coorte de startups (F3.10) reusa o mesmo Qdrant numa coleção
# **separada** — KB de tecnologia (alvo de recomendação) não se mistura com perfis de empresa.
KB_COLLECTION = "tapi_kb"

# Nomes dos vetores na coleção híbrida do Qdrant (denso nv-embedqa + esparso BM25).
DENSE_VECTOR = "dense"
SPARSE_VECTOR = "bm25"

# Espaço de índices do vetor esparso (uint32 do Qdrant). O id de cada termo é um hash estável
# nesse espaço — reproduzível entre processos, sem vocabulário sequencial a versionar.
SPARSE_INDEX_SPACE = 2**32

# Parâmetros BM25 padrão (Robertson/Spärck Jones): saturação de tf (k1) e normalização por
# tamanho do documento (b). Valores clássicos, estáveis o bastante p/ a espinha verde.
BM25_K1 = 1.5
BM25_B = 0.75

_TOKEN = re.compile(r"\w+", re.UNICODE)


class IndexUnavailable(RuntimeError):
    """Backend de índice sem infra (dep `qdrant-client` ou servidor `qdrant_url` ausente).

    Sinaliza que o Qdrant não pode indexar/buscar **agora** — análogo ao `EmbedderUnavailable`
    (F3.3) e ao `TranscriberUnavailable` (F3.1b). Offline o pipeline usa o `InMemoryVectorIndex`;
    não é erro de programação, é o ponto de degradação gracioso da infra de índice.
    """


def _tokenize(text: str) -> list[str]:
    """Tokenização determinística (NFC, minúsculas, palavras Unicode) — igual ao embed (F3.3)."""
    return _TOKEN.findall(unicodedata.normalize("NFC", text).lower())


def _term_id(token: str) -> int:
    """Id estável de um termo no espaço esparso (hashlib → reproduzível entre processos)."""
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "big") % SPARSE_INDEX_SPACE


class SparseVector(BaseModel):
    """Vetor esparso BM25 (formato do Qdrant): índices de termo + valores, alinhados e ordenados.

    `indices` é crescente e sem repetição (colisões de hash de termo são somadas no valor), como
    o Qdrant espera. O produto interno consulta×documento reconstrói o score BM25 (F3.5).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    indices: tuple[int, ...] = Field(default=(), description="Ids de termo (crescentes, únicos).")
    values: tuple[float, ...] = Field(default=(), description="Pesos BM25 alinhados a `indices`.")

    @property
    def nnz(self) -> int:
        """Número de termos não-zero (densidade do vetor esparso)."""
        return len(self.indices)


def _to_sparse(weights: dict[int, float]) -> SparseVector:
    """Empacota {id_termo: peso} num `SparseVector` com índices ordenados (contrato do Qdrant)."""
    if not weights:
        return SparseVector()
    items = sorted(weights.items())
    return SparseVector(
        indices=tuple(idx for idx, _ in items),
        values=tuple(val for _, val in items),
    )


class BM25Encoder(BaseModel):
    """Codificador esparso BM25 puro e determinístico (espinha verde lexical, F3.4).

    `fit` ajusta as estatísticas da coorte (frequência de documento → idf, comprimento médio);
    `encode_document` gera o vetor BM25 do documento (com saturação de tf e normalização por
    tamanho) e `encode_query` o vetor binário da consulta. O produto interno dos dois é o score
    BM25 — é assim que o Qdrant casa esparso×esparso, então a F3.5 reusa este encoder na busca.
    Sem rede/dep externa; o id de cada termo é um hash estável (reproduzível entre processos).
    """

    model_config = ConfigDict(extra="forbid")

    k1: float = BM25_K1
    b: float = BM25_B
    avgdl: float = 0.0
    idf: dict[str, float] = Field(default_factory=dict)

    def fit(self, texts: Sequence[str]) -> BM25Encoder:
        """Ajusta idf (df por termo) e o comprimento médio (avgdl) sobre a coorte de documentos."""
        n_docs = len(texts)
        doc_freq: Counter[str] = Counter()
        total_len = 0
        for text in texts:
            tokens = _tokenize(text)
            total_len += len(tokens)
            for token in set(tokens):
                doc_freq[token] += 1
        self.avgdl = (total_len / n_docs) if n_docs else 0.0
        # idf BM25 com +0.5 (sempre positivo via log(1+x)): termo raro pesa mais que comum.
        self.idf = {
            token: math.log(1 + (n_docs - df + 0.5) / (df + 0.5)) for token, df in doc_freq.items()
        }
        return self

    def encode_document(self, text: str) -> SparseVector:
        """Vetor esparso BM25 de um documento: idf × saturação de tf normalizada por tamanho."""
        tokens = _tokenize(text)
        dl = len(tokens)
        if not dl:
            return SparseVector()
        len_norm = self.k1 * (1 - self.b + self.b * (dl / self.avgdl if self.avgdl else 0.0))
        weights: dict[int, float] = {}
        for token, tf in Counter(tokens).items():
            idf = self.idf.get(token)
            if idf is None:
                continue  # termo fora da coorte ajustada (não casa nada na busca)
            weight = idf * (tf * (self.k1 + 1)) / (tf + len_norm)
            weights[_term_id(token)] = weights.get(_term_id(token), 0.0) + weight
        return _to_sparse(weights)

    def encode_query(self, text: str) -> SparseVector:
        """Vetor binário da consulta: 1.0 por termo conhecido — produto interno = score BM25."""
        weights: dict[int, float] = {}
        for token in set(_tokenize(text)):
            if token in self.idf:
                weights[_term_id(token)] = 1.0
        return _to_sparse(weights)


class IndexedChunk(BaseModel):
    """Unidade indexada da F3.4: o `EmbeddedChunk` (F3.3) + seu vetor esparso BM25.

    `dense` (nv-embedqa) e `sparse` (BM25) são os dois vetores do ponto híbrido no Qdrant;
    `payload` carrega a proveniência herdada do chunk p/ citar a recuperação (F3.7, §8).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    embedded: EmbeddedChunk
    sparse: SparseVector

    @property
    def chunk_id(self) -> str:
        return self.embedded.chunk_id

    @property
    def dense(self) -> tuple[float, ...]:
        return self.embedded.vector

    @property
    def payload(self) -> dict:
        """Proveniência auto-suficiente p/ citar (§8): tech/url/seção + texto fiel + modelo."""
        chunk = self.embedded.chunk
        return {
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "tech": chunk.tech,
            "title": chunk.title,
            "url": chunk.url,
            "section": chunk.section,
            "source_type": chunk.source_type,
            "heading": chunk.heading,
            "breadcrumb": list(chunk.breadcrumb),
            "text": chunk.text,
            "content_sha256": chunk.content_sha256,
            "embed_model": self.embedded.model,
        }


@runtime_checkable
class VectorIndex(Protocol):
    """Contrato de um índice híbrido (peça plugável): in-memory (espinha) ou Qdrant (dogfood)."""

    name: str

    def upsert(self, points: Sequence[IndexedChunk]) -> int:
        """Indexa os pontos (idempotente por `chunk_id`); devolve quantos foram escritos."""
        ...

    def count(self) -> int:
        """Quantos pontos distintos estão indexados."""
        ...


class InMemoryVectorIndex:
    """Índice híbrido offline (espinha verde) — guarda os pontos em memória p/ a F3.5 buscar.

    Upsert idempotente por `chunk_id` (re-indexar o mesmo chunk substitui, não duplica — dedup
    como o `content_sha256` da F3.2). Sem rede/servidor: a busca híbrida (F3.5) lê `.points`.
    """

    name = "in-memory"

    def __init__(self) -> None:
        self._points: dict[str, IndexedChunk] = {}

    def upsert(self, points: Sequence[IndexedChunk]) -> int:
        for point in points:
            self._points[point.chunk_id] = point
        return len(points)

    def count(self) -> int:
        return len(self._points)

    @property
    def points(self) -> tuple[IndexedChunk, ...]:
        """Pontos indexados (ordem de inserção) — superfície de leitura da busca híbrida (F3.5)."""
        return tuple(self._points.values())


class QdrantVectorIndex:
    """Backend **preferido** (dogfood): coleção híbrida no Qdrant (denso nv-embedqa + esparso BM25).

    Hook de rede: exige `qdrant-client` + servidor em `qdrant_url`. Cria a coleção (vetor nomeado
    `dense` cosseno + vetor esparso `bm25`) no 1º upsert, inferindo a dimensão densa do ponto, e
    grava cada chunk como ponto com payload de proveniência. Levanta `IndexUnavailable` quando a
    dep/servidor falta, p/ o pipeline cair no `InMemoryVectorIndex` offline (degrada limpo).
    """

    name = "qdrant"

    def __init__(self, *, url: str | None = None, collection: str | None = None) -> None:
        s = get_settings()
        self.url = url or s.qdrant_url
        self.collection = collection or s.qdrant_collection
        self._client = None  # construído lazy no 1º uso (degrada limpo offline)

    def _ensure_client(self):  # noqa: ANN202 - tipo da lib opcional
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:  # dep opcional ausente -> degrada p/ offline
            raise IndexUnavailable(
                "qdrant: qdrant-client não instalado (hook de rede F3.4); "
                "offline o RAG usa o InMemoryVectorIndex."
            ) from exc
        try:
            client = QdrantClient(url=self.url)
            client.get_collections()  # ping: falha cedo se o servidor não responde
        except Exception as exc:  # noqa: BLE001 - qualquer falha de conexão degrada p/ offline
            raise IndexUnavailable(
                f"qdrant: servidor em {self.url} indisponível (hook de rede F3.4); "
                "offline o RAG usa o InMemoryVectorIndex."
            ) from exc
        self._client = client
        return client

    def _ensure_collection(self, dimension: int) -> None:
        from qdrant_client import models

        client = self._ensure_client()
        if client.collection_exists(self.collection):
            return
        client.create_collection(
            self.collection,
            vectors_config={
                DENSE_VECTOR: models.VectorParams(
                    size=dimension, distance=models.Distance.COSINE
                )
            },
            sparse_vectors_config={SPARSE_VECTOR: models.SparseVectorParams()},
        )

    def upsert(self, points: Sequence[IndexedChunk]) -> int:
        if not points:
            return 0
        from qdrant_client import models

        self._ensure_collection(len(points[0].dense))
        client = self._ensure_client()
        struct = [
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, point.chunk_id)),
                vector={
                    DENSE_VECTOR: list(point.dense),
                    SPARSE_VECTOR: models.SparseVector(
                        indices=list(point.sparse.indices),
                        values=list(point.sparse.values),
                    ),
                },
                payload=point.payload,
            )
            for point in points
        ]
        client.upsert(self.collection, points=struct)
        return len(struct)

    def count(self) -> int:
        client = self._ensure_client()
        if not client.collection_exists(self.collection):
            return 0
        return client.count(self.collection).count


def get_index(*, prefer_qdrant: bool | None = None) -> VectorIndex:
    """Escolhe o índice: Qdrant (rede) se ligado, senão o in-memory offline (espinha verde).

    Default vem de `index_use_qdrant` (config, off por default). `prefer_qdrant` sobrepõe (demo).
    Nunca levanta aqui — o `QdrantVectorIndex` só falha quando usado sem a dep/servidor.
    """
    use_qdrant = get_settings().index_use_qdrant if prefer_qdrant is None else prefer_qdrant
    return QdrantVectorIndex() if use_qdrant else InMemoryVectorIndex()


def index_chunks(
    embedded: Sequence[EmbeddedChunk],
    *,
    index: VectorIndex | None = None,
    encoder: BM25Encoder | None = None,
) -> tuple[VectorIndex, BM25Encoder]:
    """Indexa `EmbeddedChunk` (F3.3) como pontos híbridos (denso + BM25) no índice escolhido.

    Ajusta o `BM25Encoder` sobre o `contextual_text` da coorte (a mesma superfície que a F3.3
    embeda — breadcrumb + corpo, p/ tech/seção contarem no lexical) e devolve o índice já
    preenchido + o encoder ajustado (a F3.5 reusa o encoder p/ codificar a consulta).
    """
    embedded = tuple(embedded)
    texts = [e.chunk.contextual_text for e in embedded]
    encoder = encoder or BM25Encoder().fit(texts)
    index = index if index is not None else get_index()
    points = tuple(
        IndexedChunk(embedded=e, sparse=encoder.encode_document(text))
        for e, text in zip(embedded, texts, strict=True)
    )
    index.upsert(points)
    return index, encoder


def build_index(
    *,
    embedded: Sequence[EmbeddedChunk] | None = None,
    index: VectorIndex | None = None,
    encoder: BM25Encoder | None = None,
) -> tuple[VectorIndex, BM25Encoder]:
    """Pipeline F3.1→F3.2→F3.3→F3.4: ingere, chunkifica, embeda e indexa a KB inteira.

    Com o embedder e o índice offline default é reproduzível e roda sem rede (base p/ a F3.5).
    """
    embedded = embed_kb() if embedded is None else embedded
    return index_chunks(embedded, index=index, encoder=encoder)


__all__ = [
    "KB_COLLECTION",
    "DENSE_VECTOR",
    "SPARSE_VECTOR",
    "SPARSE_INDEX_SPACE",
    "BM25_K1",
    "BM25_B",
    "IndexUnavailable",
    "SparseVector",
    "BM25Encoder",
    "IndexedChunk",
    "VectorIndex",
    "InMemoryVectorIndex",
    "QdrantVectorIndex",
    "get_index",
    "index_chunks",
    "build_index",
]
