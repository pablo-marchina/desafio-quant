"""Embeddings da KB com NeMo Retriever nv-embedqa (F3.3).

Terceira etapa do pipeline RAG (ARQUITETURA §4): pega os `Chunk` semânticos (F3.2) e os
transforma em vetores prontos p/ indexar no Qdrant (F3.4) e recuperar na busca híbrida
(F3.5). O backend **preferido** (dogfood/narrativa) é o **NeMo Retriever
`nvidia/llama-nemotron-embed-1b-v2`** (multilíngue, embedding assimétrico query×passage;
sucessor do `nv-embedqa-1b-v2`, que atingiu EOL em 2026-05-18).

Decisões (F3.3), honrando o que já está travado no projeto:

- **Interface plugável `Embedder`** (mesmo trade-off de infra que o `Transcriber`/F3.1b e o
  futuro `Reranker`/F3.6): `embed_passages` (indexação) e `embed_query` (recuperação) —
  **assimétrico**, como o nv-embedqa pede (`input_type` passage×query). O modelo que gerou o
  vetor entra no `EmbeddedChunk` como proveniência.
- **O backend real é um hook de rede/GPU que degrada limpo** — como o `RivaTranscriber`
  (F3.1b) e `scraper_use_network` (F2.4) ficam *off* por default: `NVEmbedQA` exige
  `NVIDIA_API_KEY` (catálogo build.nvidia.com) ou o NIM self-hosted (GPU local), e levanta
  `EmbedderUnavailable` quando a infra falta. O build/CI nunca trava na rede.
- **Espinha verde offline e determinística** (decisão travada desde a F3.1): o default é o
  `HashingEmbedder` — feature hashing puro (sem rede/credencial/GPU), **reproduzível** entre
  processos (hash estável via `hashlib`, não o `hash()` randômico) e com cosseno significativo
  (vocabulário compartilhado → mais perto), para a espinha de F3.4/F3.5 rodar e ser testada
  offline. Troca-se pelo nv-embedqa via config (`embeddings_use_nv`) ou injeção, sem mexer no
  resto do pipeline (peça plugável). Liga-se ao nv-embedqa de verdade na demo/com GPU.
- **Texto embedado = `Chunk.contextual_text`** (decisão da F3.2): o breadcrumb de títulos é
  prefixado ao corpo, então o vetor "sabe" a que tech/seção o trecho pertence. A citação fiel
  (`text`) segue intacta no chunk para a resposta com fontes (F3.7).
- **I/O tipado** (Pydantic): `EmbeddedChunk` casa o `Chunk` (proveniência auto-suficiente) com
  o vetor e o `model` — a unidade que a F3.4 indexa no Qdrant.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from packages.config import get_settings

from .chunk import Chunk, chunk_kb

# Dimensão do NeMo Retriever (llama-nemotron-embed-1b-v2, = a do nv-embedqa-1b-v2 anterior).
# O que vale no índice (F3.4) é o comprimento real do vetor / `embedder.dimension`; referência.
NV_EMBEDQA_DIM = 2048

# Dimensão do embedder offline determinístico: grande o bastante p/ colisões raras de hashing,
# pequena o bastante p/ ser barata na espinha verde (não é o vetor de produção).
DEFAULT_OFFLINE_DIM = 256

_TOKEN = re.compile(r"\w+", re.UNICODE)


class EmbedderUnavailable(RuntimeError):
    """Backend de embedding sem infra (credencial/endpoint/deps).

    Sinaliza que o backend de rede/GPU não pode embedar **agora** — análogo ao
    `TranscriberUnavailable` (F3.1b). Offline o pipeline usa o `HashingEmbedder`; não é erro de
    programação, é o ponto de degradação gracioso da infra de embeddings.
    """


@runtime_checkable
class Embedder(Protocol):
    """Contrato de um backend de embedding (peça plugável).

    Assimétrico de propósito (o nv-embedqa distingue `input_type` passage×query): `name`/`model`
    identificam o backend no trace e na proveniência; `dimension` configura o índice (F3.4).
    """

    name: str
    model: str
    dimension: int

    def embed_passages(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        """Embeda trechos da KB para indexação (`input_type=passage`)."""
        ...

    def embed_query(self, text: str) -> tuple[float, ...]:
        """Embeda uma consulta para recuperação (`input_type=query`)."""
        ...


class EmbeddedChunk(BaseModel):
    """Unidade indexável da F3.4: um `Chunk` (F3.2) + seu vetor + o modelo que o gerou.

    Mantém o `Chunk` aninhado (proveniência auto-suficiente: url/tech/section/hash) e carimba o
    `model` do embedding como proveniência do vetor — nenhuma recuperação sem fonte rastreável (§8).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk: Chunk
    model: str = Field(description="Modelo de embedding que gerou o vetor (proveniência).")
    vector: tuple[float, ...] = Field(description="Vetor denso do `contextual_text` do chunk.")

    @property
    def chunk_id(self) -> str:
        """Atalho p/ o ID estável do chunk (ponto/ID no Qdrant, F3.4)."""
        return self.chunk.chunk_id

    @property
    def dimension(self) -> int:
        return len(self.vector)


def _tokenize(text: str) -> list[str]:
    """Tokenização determinística p/ o feature hashing: NFC, minúsculas, palavras Unicode."""
    return _TOKEN.findall(unicodedata.normalize("NFC", text).lower())


class HashingEmbedder:
    """Embedder offline determinístico (espinha verde) — feature hashing L2-normalizado.

    Sem rede/credencial/GPU e **reproduzível entre processos** (hash estável via `hashlib`, não
    o `hash()` randômico do Python). Cosseno significativo (trechos com vocabulário em comum
    ficam mais perto), o bastante p/ exercitar e testar F3.4/F3.5 offline. **Simétrico** (query
    e passagem embedados igual) — diferente do nv-embedqa real, que é assimétrico.
    """

    name = "hashing-offline"
    model = "tapi-hashing-v1"

    def __init__(self, dimension: int = DEFAULT_OFFLINE_DIM) -> None:
        if dimension <= 0:
            raise ValueError("dimension deve ser > 0")
        self.dimension = dimension

    def _embed(self, text: str) -> tuple[float, ...]:
        vec = [0.0] * self.dimension
        for token in _tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0  # hashing com sinal: reduz viés de colisão
            vec[idx] += sign
        norm = math.sqrt(sum(value * value for value in vec))
        if norm == 0.0:
            return tuple(vec)  # texto sem tokens -> vetor zero (caso degenerado)
        return tuple(value / norm for value in vec)

    def embed_passages(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return tuple(self._embed(text) for text in texts)

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self._embed(text)


class NVEmbedQA:
    """Backend **preferido** (dogfood): NeMo Retriever nv-embedqa via build.nvidia.com ou NIM.

    Hook de rede/GPU: usa o catálogo (`NVIDIA_API_KEY`) ou o NIM self-hosted (`NIM_BASE_URL`,
    GPU local). Levanta `EmbedderUnavailable` quando a credencial/endpoint/dep falta, p/ o
    pipeline cair no `HashingEmbedder` offline. Assimétrico: `embed_documents`/`embed_query` do
    `NVIDIAEmbeddings` carimbam `input_type` passage×query.
    """

    name = "nv-embedqa"
    dimension = NV_EMBEDQA_DIM

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        self_hosted: bool = False,
        truncate: str = "END",
    ) -> None:
        s = get_settings()
        self.model = model or s.nv_embed_model
        self.api_key = api_key if api_key is not None else s.nvidia_api_key
        self.self_hosted = self_hosted
        self.base_url = s.nim_base_url if self_hosted else None
        self.truncate = truncate
        self._client = None  # construído lazy no 1º uso (degrada limpo offline)

    def _ensure_client(self):  # noqa: ANN202 - tipo da lib opcional
        if self._client is not None:
            return self._client
        try:
            from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
        except ImportError as exc:  # dep opcional ausente -> degrada p/ offline
            raise EmbedderUnavailable(
                "nv-embedqa: langchain-nvidia-ai-endpoints não instalado (hook de rede F3.3); "
                "offline o RAG usa o HashingEmbedder."
            ) from exc
        if not self.self_hosted and not self.api_key:
            raise EmbedderUnavailable(
                "nv-embedqa: NVIDIA_API_KEY ausente (catálogo build.nvidia.com) e sem NIM "
                "self-hosted — hook de rede/GPU F3.3; offline o RAG usa o HashingEmbedder."
            )
        kwargs: dict = {"model": self.model, "truncate": self.truncate}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        elif self.api_key:
            kwargs["api_key"] = self.api_key
        self._client = NVIDIAEmbeddings(**kwargs)
        return self._client

    def embed_passages(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        client = self._ensure_client()
        return tuple(tuple(vec) for vec in client.embed_documents(list(texts)))

    def embed_query(self, text: str) -> tuple[float, ...]:
        client = self._ensure_client()
        return tuple(client.embed_query(text))


def get_embedder(*, prefer_nv: bool | None = None) -> Embedder:
    """Escolhe o embedder: nv-embedqa (rede/GPU) se ligado, senão o offline determinístico.

    Default vem de `embeddings_use_nv` (config, off por default = espinha verde). `prefer_nv`
    sobrepõe (p/ a demo/GPU). Nunca levanta aqui — o `NVEmbedQA` só falha quando usado offline.
    """
    use_nv = get_settings().embeddings_use_nv if prefer_nv is None else prefer_nv
    return NVEmbedQA() if use_nv else HashingEmbedder()


def embed_chunks(
    chunks: Sequence[Chunk], *, embedder: Embedder | None = None
) -> tuple[EmbeddedChunk, ...]:
    """Embeda uma sequência de `Chunk` (F3.2) -> `EmbeddedChunk` prontos p/ o Qdrant (F3.4).

    Embeda o `contextual_text` (breadcrumb + corpo, decisão da F3.2) e carimba o `model` no
    resultado. Determinístico com o embedder offline default; assimétrico (passage) no nv-embedqa.
    """
    embedder = embedder or get_embedder()
    if not chunks:
        return ()
    vectors = embedder.embed_passages([chunk.contextual_text for chunk in chunks])
    return tuple(
        EmbeddedChunk(chunk=chunk, model=embedder.model, vector=vector)
        for chunk, vector in zip(chunks, vectors, strict=True)
    )


def embed_query(text: str, *, embedder: Embedder | None = None) -> tuple[float, ...]:
    """Embeda uma consulta p/ recuperação (F3.5/F3.7), `input_type=query` no nv-embedqa."""
    embedder = embedder or get_embedder()
    return embedder.embed_query(text)


def embed_kb(*, embedder: Embedder | None = None) -> tuple[EmbeddedChunk, ...]:
    """Pipeline F3.1→F3.2→F3.3: ingere, chunkifica e embeda a KB inteira.

    Com o embedder offline default é reproduzível e roda sem rede (base p/ testar F3.4/F3.5).
    """
    return embed_chunks(chunk_kb(), embedder=embedder)


__all__ = [
    "NV_EMBEDQA_DIM",
    "DEFAULT_OFFLINE_DIM",
    "EmbedderUnavailable",
    "Embedder",
    "EmbeddedChunk",
    "HashingEmbedder",
    "NVEmbedQA",
    "get_embedder",
    "embed_chunks",
    "embed_query",
    "embed_kb",
]
