"""Reranking da KB com NeMo Reranking NIM (F3.6).

Sexta etapa do pipeline RAG (ARQUITETURA §4): pega os `RetrievedChunk` que a busca híbrida
(F3.5) trouxe e os **reordena pela relevância real à consulta**, antes da resposta com
citações (F3.7). A busca híbrida funde dois sinais *de recuperação* (denso + lexical) por
posição (RRF); o reranker é um **cross-encoder** que lê a consulta e o trecho **juntos** e
estima a relevância de cada par — um sinal mais fino, que costuma corrigir a ordem grosseira
da fusão antes de gastar contexto do LLM. O backend **preferido** (dogfood/narrativa) é o
**NeMo Reranking NIM** `nvidia/llama-nemotron-rerank-1b-v2` (default no build; sucessor do
`nv-rerankqa-1b-v2`, que atingiu EOL em 2026-05-18).

Decisões (F3.6), honrando o que já está travado no projeto:

- **Interface plugável `Reranker`** (mesmo trade-off de infra do `Embedder`/F3.3 e do
  `Transcriber`/F3.1b): `rerank(query, chunks)` devolve os trechos reordenados com um
  `rerank_score`. O backend que pontuou entra no `RerankedChunk` como proveniência (§8).
- **Backend real é hook de rede/GPU que degrada limpo** — como o `NVEmbedQA` (F3.3), o
  `QdrantVectorIndex` (F3.4) e o `RivaTranscriber` (F3.1b): `NeMoReranker` exige
  `NVIDIA_API_KEY` (catálogo build.nvidia.com) ou o NIM self-hosted (GPU local), e levanta
  `RerankerUnavailable` quando a infra falta. O build/CI nunca trava na rede.
- **Espinha verde offline e determinística** (travada desde a F3.1): o default é o
  `LexicalReranker` — um **substituto de cross-encoder puramente lexical**, sem rede/GPU e
  **reproduzível entre processos**, para a F3.7 rodar e ser testada offline. Ele pontua a
  consulta×trecho pela cobertura dos termos da consulta *ponderada pelo idf local da janela
  de candidatos* (os termos que **discriminam** entre os candidatos pesam mais) — um sinal
  distinto do BM25 global da F3.5 (que casa contra a coorte inteira), então reordenar de fato
  muda a ordem. O valor real (relevância semântica do cross-encoder) vem do NeMo NIM; o offline
  é a espinha que mantém o pipeline verde. Troca-se por config (`reranker_use_nv`) ou injeção.
- **Provider plugável** (`reranker_provider`): `nemo` é o default no build; **Cohere Rerank é
  da F7** (comparativo NeMo×Cohere) — o caminho fica reservado aqui e levanta `RerankerUnavailable`
  até a F7 ligá-lo, sem antecipar trabalho de outra fase.
- **Resultado auto-suficiente p/ citar** (§8): `RerankedChunk` carrega o `RetrievedChunk`
  original (proveniência herdada: tech/url/seção/texto + modelos) + o `rerank_score`; a F3.7
  cita direto dele. O `retrieval_score` (fundido da F3.5) fica exposto p/ transparência.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from packages.config import get_settings

from .retrieve import RetrievedChunk

_TOKEN = re.compile(r"\w+", re.UNICODE)


class RerankerUnavailable(RuntimeError):
    """Backend de rerank sem infra (credencial/endpoint/dep).

    Sinaliza que o backend de rede/GPU não pode reordenar **agora** — análogo ao
    `EmbedderUnavailable` (F3.3) e ao `IndexUnavailable` (F3.4). Offline o pipeline usa o
    `LexicalReranker`; não é erro de programação, é o ponto de degradação gracioso da infra
    de reranking. Também sinaliza um provider ainda não ligado (Cohere é da F7).
    """


def _tokenize(text: str) -> list[str]:
    """Tokenização determinística (NFC, minúsculas, palavras Unicode) — igual ao embed/index."""
    return _TOKEN.findall(unicodedata.normalize("NFC", text).lower())


def _rerank_surface(chunk: RetrievedChunk) -> str:
    """Superfície que o cross-encoder lê: caminho de títulos + corpo (igual ao `contextual_text`).

    Espelha o que a F3.2/F3.3 embedaram (breadcrumb + texto), para a relevância de um trecho de
    bullets contar o contexto de tech/seção a que ele pertence — e não só o corpo literal.
    """
    breadcrumb = chunk.payload.get("breadcrumb") or []
    if breadcrumb:
        return " > ".join(breadcrumb) + "\n\n" + chunk.text
    return chunk.text


class RerankedChunk(BaseModel):
    """Trecho reordenado pelo reranker (F3.6) — pronto p/ a resposta com citações (F3.7).

    Aninha o `RetrievedChunk` da F3.5 (proveniência auto-suficiente) e carimba o `rerank_score`
    que ordena o resultado. `retrieval_score` (o fundido RRF da F3.5) fica exposto p/ transparência
    — dá p/ ver o reranker corrigindo a ordem da fusão.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    retrieved: RetrievedChunk
    rerank_score: float = Field(description="Relevância consulta×trecho — ordenação final (F3.6).")

    @property
    def chunk_id(self) -> str:
        return self.retrieved.chunk_id

    @property
    def retrieval_score(self) -> float:
        """Score fundido (RRF) que a F3.5 atribuiu — antes do rerank (transparência)."""
        return self.retrieved.score

    @property
    def payload(self) -> dict:
        return self.retrieved.payload

    @property
    def text(self) -> str:
        return self.retrieved.text

    @property
    def tech(self) -> str:
        return self.retrieved.tech

    @property
    def url(self) -> str:
        return self.retrieved.url

    @property
    def section(self) -> str:
        return self.retrieved.section

    @property
    def title(self) -> str:
        return self.retrieved.title

    @property
    def source_type(self) -> str:
        return self.retrieved.source_type


@runtime_checkable
class Reranker(Protocol):
    """Contrato de um backend de rerank (peça plugável).

    `name`/`model` identificam o backend no trace e na proveniência (§8); `rerank` reordena os
    `RetrievedChunk` (F3.5) pela relevância à consulta e corta no `top_n` (None = todos).
    """

    name: str
    model: str

    def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], *, top_n: int | None = None
    ) -> tuple[RerankedChunk, ...]:
        """Reordena os trechos pela relevância à consulta; devolve até `top_n` (None = todos)."""
        ...


def _order(
    scored: Sequence[tuple[RetrievedChunk, float]], top_n: int | None
) -> tuple[RerankedChunk, ...]:
    """Ordena (trecho, score) desc — desempate pelo score de recuperação (F3.5) e o id — e corta."""
    ordered = sorted(scored, key=lambda it: (-it[1], -it[0].score, it[0].chunk_id))
    if top_n is not None:
        ordered = ordered[:top_n]
    return tuple(
        RerankedChunk(retrieved=chunk, rerank_score=score) for chunk, score in ordered
    )


class LexicalReranker:
    """Reranker offline determinístico (espinha verde) — substituto de cross-encoder lexical.

    Sem rede/credencial/GPU e **reproduzível entre processos**. Pontua a relevância consulta×trecho
    pela **cobertura dos termos da consulta ponderada pelo idf local** da janela de candidatos: os
    termos da consulta que aparecem em poucos candidatos (discriminativos) pesam mais que os que
    aparecem em todos. O score é a fração dessa massa discriminativa que o trecho cobre (∈[0, 1]).
    Sinal distinto do BM25 global da F3.5 (que casa contra a coorte inteira), então o rerank
    reordena de fato. **Não** é semântico — o valor real é o `NeMoReranker`; este é a espinha.
    """

    name = "lexical-offline"
    model = "tapi-lexical-rerank-v1"

    def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], *, top_n: int | None = None
    ) -> tuple[RerankedChunk, ...]:
        chunks = tuple(chunks)
        if not chunks:
            return ()
        query_terms = set(_tokenize(query))
        candidate_tokens = [set(_tokenize(_rerank_surface(c))) for c in chunks]
        n = len(chunks)
        # df local: em quantos candidatos cada termo da consulta aparece (só termos da consulta).
        doc_freq: Counter[str] = Counter()
        for tokens in candidate_tokens:
            for term in tokens & query_terms:
                doc_freq[term] += 1
        # idf local suavizado: termo presente em poucos candidatos discrimina mais (peso maior).
        idf = {term: math.log((n + 1) / (df + 0.5)) + 1.0 for term, df in doc_freq.items()}
        total = sum(idf.values())  # massa discriminativa presente na janela de candidatos
        scored = [
            (
                chunk,
                (sum(idf[t] for t in tokens & query_terms) / total) if total else 0.0,
            )
            for chunk, tokens in zip(chunks, candidate_tokens, strict=True)
        ]
        return _order(scored, top_n)


class NeMoReranker:
    """Backend **preferido** (dogfood): NeMo Reranking NIM nv-rerankqa via build.nvidia.com ou NIM.

    Hook de rede/GPU: usa o catálogo (`NVIDIA_API_KEY`) ou o NIM self-hosted (`NIM_BASE_URL`,
    GPU local). Cross-encoder de verdade — lê consulta+trecho juntos e devolve `relevance_score`.
    Levanta `RerankerUnavailable` quando a credencial/endpoint/dep falta, p/ o pipeline cair no
    `LexicalReranker` offline. Usa o `NVIDIARerank` do `langchain-nvidia-ai-endpoints`.
    """

    name = "nv-rerankqa"

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        self_hosted: bool = False,
        truncate: str = "END",
    ) -> None:
        s = get_settings()
        self.model = model or s.nv_rerank_model
        self.api_key = api_key if api_key is not None else s.nvidia_api_key
        self.self_hosted = self_hosted
        self.base_url = s.nim_base_url if self_hosted else None
        self.truncate = truncate
        self._client = None  # construído lazy no 1º uso (degrada limpo offline)

    def _ensure_client(self):  # noqa: ANN202 - tipo da lib opcional
        if self._client is not None:
            return self._client
        try:
            from langchain_nvidia_ai_endpoints import NVIDIARerank
        except ImportError as exc:  # dep opcional ausente -> degrada p/ offline
            raise RerankerUnavailable(
                "nv-rerankqa: langchain-nvidia-ai-endpoints não instalado (hook de rede F3.6); "
                "offline o RAG usa o LexicalReranker."
            ) from exc
        if not self.self_hosted and not self.api_key:
            raise RerankerUnavailable(
                "nv-rerankqa: NVIDIA_API_KEY ausente (catálogo build.nvidia.com) e sem NIM "
                "self-hosted — hook de rede/GPU F3.6; offline o RAG usa o LexicalReranker."
            )
        kwargs: dict = {"model": self.model, "truncate": self.truncate}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        elif self.api_key:
            kwargs["api_key"] = self.api_key
        self._client = NVIDIARerank(**kwargs)
        return self._client

    def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], *, top_n: int | None = None
    ) -> tuple[RerankedChunk, ...]:
        chunks = tuple(chunks)
        if not chunks:
            return ()
        from langchain_core.documents import Document

        client = self._ensure_client()
        # top_n é atributo do NVIDIARerank; o cross-encoder NIM já corta no servidor.
        client.top_n = len(chunks) if top_n is None else top_n
        # `_idx` mapeia o doc reordenado de volta ao RetrievedChunk (o texto pode repetir).
        docs = [
            Document(page_content=_rerank_surface(c), metadata={"_idx": i})
            for i, c in enumerate(chunks)
        ]
        ranked = client.compress_documents(query=query, documents=docs)
        return tuple(
            RerankedChunk(
                retrieved=chunks[doc.metadata["_idx"]],
                rerank_score=float(doc.metadata.get("relevance_score", 0.0)),
            )
            for doc in ranked
        )


#: Retry do 429 (rate limit) do Cohere — a **trial key** é limitada a 10 req/min, e o comparativo
#: F7.4 faz ~2 chamadas por pergunta. Em vez de crashar (o 429 não é `RerankerUnavailable`),
#: espera-se a janela deslizante rolar e re-tenta; esgotado, degrada limpo p/ o `LexicalReranker`.
_COHERE_RL_RETRIES = 12
_COHERE_RL_WAIT_S = 7.0


class CohereReranker:
    """Backend **alternativo** (comparativo F7.4): Cohere Rerank — cross-encoder gerenciado.

    O brief nomeia a Cohere no §5.3, então o comparativo NeMo×Cohere (qualidade × custo × latência)
    é item de destaque no relatório (F7.5): justifica a escolha do NeMo no build **com dados**, não
    por omissão. Hook de rede idêntico ao `NeMoReranker`: usa a `cohere_api_key` (trial) e o modelo
    **multilíngue** (`rerank-multilingual-v3.0`) p/ casar o conteúdo PT-BR/EN da KB. Levanta
    `RerankerUnavailable` quando a dep `cohere`/a credencial falta — o pipeline cai no
    `LexicalReranker` offline (mesma disciplina da espinha verde). Usa o SDK `cohere` (ClientV2).
    """

    name = "cohere-rerank"

    def __init__(self, *, model: str | None = None, api_key: str | None = None) -> None:
        s = get_settings()
        self.model = model or s.cohere_rerank_model
        self.api_key = api_key if api_key is not None else s.cohere_api_key
        self._client = None  # construído lazy no 1º uso (degrada limpo offline)

    def _ensure_client(self):  # noqa: ANN202 - tipo da lib opcional
        if self._client is not None:
            return self._client
        try:
            import cohere
        except ImportError as exc:  # dep opcional ausente -> degrada p/ offline
            raise RerankerUnavailable(
                "cohere-rerank: SDK `cohere` não instalado (comparativo F7.4); offline o RAG usa "
                "o LexicalReranker."
            ) from exc
        if not self.api_key:
            raise RerankerUnavailable(
                "cohere-rerank: COHERE_API_KEY ausente (trial, comparativo F7.4); offline o RAG "
                "usa o LexicalReranker."
            )
        self._client = cohere.ClientV2(api_key=self.api_key)
        return self._client

    def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], *, top_n: int | None = None
    ) -> tuple[RerankedChunk, ...]:
        chunks = tuple(chunks)
        if not chunks:
            return ()
        client = self._ensure_client()
        documents = [_rerank_surface(c) for c in chunks]
        result = self._rerank_with_retry(
            client, query, documents, top_n=len(chunks) if top_n is None else top_n
        )
        # `index` mapeia o resultado de volta ao RetrievedChunk; `relevance_score` ∈ [0,1] ordena.
        return _order(
            [(chunks[r.index], float(r.relevance_score)) for r in result.results], top_n
        )

    def _rerank_with_retry(self, client, query: str, documents: list[str], *, top_n: int):  # noqa: ANN202
        """Chama o Cohere tolerando o **429** (rate limit da trial, 10 req/min): espera e re-tenta.

        Sem isto o 429 (não é `RerankerUnavailable`) crashava o comparativo F7.4 inteiro. Espera a
        janela rolar (`_COHERE_RL_WAIT_S`) e re-tenta até `_COHERE_RL_RETRIES`; persistindo, degrada
        limpo (`RerankerUnavailable`) p/ o pipeline cair no `LexicalReranker` — nunca número falso.
        """
        import time

        from cohere.errors import TooManyRequestsError

        for attempt in range(_COHERE_RL_RETRIES):
            try:
                return client.rerank(
                    model=self.model, query=query, documents=documents, top_n=top_n
                )
            except TooManyRequestsError as exc:
                if attempt == _COHERE_RL_RETRIES - 1:
                    raise RerankerUnavailable(
                        f"cohere-rerank: rate limit da trial key persistente após "
                        f"{_COHERE_RL_RETRIES} tentativas (10 req/min); offline o RAG usa o "
                        "LexicalReranker. Use uma production key p/ medir sem espera."
                    ) from exc
                time.sleep(_COHERE_RL_WAIT_S)
        raise AssertionError("unreachable")  # o loop sempre retorna ou levanta


def get_reranker(*, prefer_nv: bool | None = None) -> Reranker:
    """Escolhe o reranker: NeMo NIM (rede/GPU) se ligado, senão o offline determinístico.

    Default vem de `reranker_use_nv` (config, off por default = espinha verde). `prefer_nv`
    sobrepõe (p/ a demo/GPU). Quando ligado, o `reranker_provider` seleciona o backend real:
    `nemo` (default no build) ou `cohere` (comparativo F7.4). Offline nunca levanta — os backends
    de rede só falham ao serem usados (degradam p/ o `LexicalReranker`).
    """
    use_nv = get_settings().reranker_use_nv if prefer_nv is None else prefer_nv
    if not use_nv:
        return LexicalReranker()
    provider = get_settings().reranker_provider
    if provider == "cohere":
        return CohereReranker()
    return NeMoReranker()


def rerank(
    query: str,
    chunks: Sequence[RetrievedChunk],
    *,
    reranker: Reranker | None = None,
    top_n: int | None = None,
) -> tuple[RerankedChunk, ...]:
    """Reordena os trechos da busca híbrida (F3.5) pela relevância à consulta (F3.6).

    Usa o reranker default (`get_reranker()` — offline/espinha verde por config) ou o injetado.
    Determinístico com o `LexicalReranker`; cross-encoder de verdade no NeMo NIM. Base p/ a F3.7.
    """
    reranker = reranker or get_reranker()
    return reranker.rerank(query, chunks, top_n=top_n)


__all__ = [
    "RerankerUnavailable",
    "Reranker",
    "RerankedChunk",
    "LexicalReranker",
    "NeMoReranker",
    "CohereReranker",
    "get_reranker",
    "rerank",
]
