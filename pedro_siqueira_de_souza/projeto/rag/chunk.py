"""Chunking do corpus NVIDIA (RAG — Entregável 3).

Por que chunkar? Modelos de embedding têm limite de contexto e — mais
importante — vetores de textos LONGOS "borram" muitos assuntos num único ponto,
piorando a recuperação. Quebrar cada doc em pedaços curtos e temáticos faz cada
vetor representar UMA ideia, o que melhora a precisão do retrieval.

Decisões de design:
  - Janela por TOKENS (tiktoken), não por caracteres: é a unidade real que o
    modelo de embedding enxerga, então o limite fica fiel ao custo/contexto.
  - OVERLAP entre janelas: evita cortar uma frase no meio e perder o contexto
    da fronteira — o fim de um chunk reaparece no começo do próximo.
  - `cl100k_base`: encoding dos modelos `text-embedding-3-*` da OpenAI.

Mantemos a aritmética de janela explícita (em vez de um TextSplitter pronto)
porque o ponto do entregável é ENTENDER o trade-off tamanho × overlap.
"""
from functools import lru_cache

import tiktoken
from pydantic import BaseModel

from rag.ingest import NvidiaDoc

# Encoding dos modelos text-embedding-3-* (OpenAI).
ENCODING_NAME = "cl100k_base"

# Defaults conservadores: ~300 tokens por chunk com 50 de sobreposição. Pequeno
# o bastante para cada vetor ser temático; grande o bastante para ter contexto.
DEFAULT_MAX_TOKENS = 300
DEFAULT_OVERLAP = 50


class Chunk(BaseModel):
    """Um pedaço de um doc, já pronto para virar um vetor no Qdrant."""

    tech: str
    url: str
    text: str
    chunk_index: int  # posição do chunk dentro do doc de origem (0, 1, 2, ...)


@lru_cache
def _encoder() -> tiktoken.Encoding:
    """Carrega o encoder uma vez (custa caro montar; cacheia)."""
    return tiktoken.get_encoding(ENCODING_NAME)


def chunk_text(
    text: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """Quebra um texto em janelas de tokens sobrepostas.

    A janela anda `max_tokens - overlap` tokens por vez, então pedaços
    consecutivos compartilham `overlap` tokens na fronteira.
    """
    if overlap >= max_tokens:
        raise ValueError("overlap precisa ser menor que max_tokens.")

    enc = _encoder()
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return [text] if text.strip() else []

    step = max_tokens - overlap
    chunks: list[str] = []
    for start in range(0, len(tokens), step):
        janela = tokens[start : start + max_tokens]
        chunks.append(enc.decode(janela).strip())
        if start + max_tokens >= len(tokens):  # já cobriu o fim — para
            break
    return chunks


def chunk_doc(
    doc: NvidiaDoc,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """Aplica `chunk_text` num doc, preservando a proveniência (tech + url)."""
    return [
        Chunk(tech=doc.tech, url=doc.url, text=pedaco, chunk_index=i)
        for i, pedaco in enumerate(chunk_text(doc.text, max_tokens, overlap))
    ]


def chunk_corpus(
    docs: list[NvidiaDoc],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """Chunka o corpus inteiro, achatando num único lista de chunks."""
    chunks: list[Chunk] = []
    for doc in docs:
        chunks.extend(chunk_doc(doc, max_tokens, overlap))
    return chunks
