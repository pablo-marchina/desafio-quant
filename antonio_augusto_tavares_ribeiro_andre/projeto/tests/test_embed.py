"""Testes dos embeddings da KB com NeMo Retriever nv-embedqa (F3.3).

Cobrem, todos offline (sem rede/credencial/GPU):

1. **Interface plugável `Embedder`** (dogfood nv-embedqa + espinha verde offline): saída tipada
   (`EmbeddedChunk`), embeda o `contextual_text` do chunk (decisão da F3.2) e carimba o `model`.
2. **Espinha verde determinística** (`HashingEmbedder`): reproduzível entre runs, normalizado, e
   com cosseno significativo (vocabulário compartilhado → mais perto) — base p/ F3.4/F3.5.
3. **Backend real degrada limpo** (`NVEmbedQA`): sem `NVIDIA_API_KEY`/NIM levanta
   `EmbedderUnavailable`, não trava o build.
"""

from __future__ import annotations

import math

import pytest

from packages.rag import (
    DEFAULT_OFFLINE_DIM,
    NV_EMBEDQA_DIM,
    EmbeddedChunk,
    Embedder,
    EmbedderUnavailable,
    HashingEmbedder,
    NVEmbedQA,
    chunk_kb,
    embed_chunks,
    embed_kb,
    embed_query,
    get_embedder,
)


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# --- Interface plugável ----------------------------------------------------------------------


def test_hashing_embedder_satisfies_protocol() -> None:
    emb = HashingEmbedder()
    assert isinstance(emb, Embedder)
    assert emb.dimension == DEFAULT_OFFLINE_DIM
    assert emb.model  # proveniência do vetor


def test_get_embedder_defaults_to_offline_spine() -> None:
    # embeddings_use_nv é off por default => espinha verde offline (sem rede).
    assert isinstance(get_embedder(), HashingEmbedder)
    assert isinstance(get_embedder(prefer_nv=True), NVEmbedQA)
    assert get_embedder(prefer_nv=True).dimension == NV_EMBEDQA_DIM


# --- Espinha verde determinística ------------------------------------------------------------


def test_hashing_is_deterministic_and_normalized() -> None:
    a = HashingEmbedder().embed_query("NVIDIA NIM serve modelos em GPU")
    b = HashingEmbedder().embed_query("NVIDIA NIM serve modelos em GPU")
    assert a == b  # reproduzível entre instâncias/processos (hashlib, não hash())
    assert len(a) == DEFAULT_OFFLINE_DIM
    assert abs(math.sqrt(sum(x * x for x in a)) - 1.0) < 1e-9  # L2-normalizado


def test_hashing_cosine_reflects_shared_vocabulary() -> None:
    emb = HashingEmbedder()
    base = emb.embed_query("inferência de LLM acelerada em GPU NVIDIA")
    near = emb.embed_query("inferência de LLM em GPU NVIDIA com NIM")
    far = emb.embed_query("receita de bolo de chocolate com morango")
    assert _cosine(base, near) > _cosine(base, far)  # vocabulário em comum -> mais perto


def test_empty_text_yields_zero_vector() -> None:
    v = HashingEmbedder().embed_query("   ")
    assert len(v) == DEFAULT_OFFLINE_DIM
    assert all(x == 0.0 for x in v)  # caso degenerado sem tokens


# --- embed_chunks / EmbeddedChunk ------------------------------------------------------------


def test_embed_chunks_embeds_contextual_text_with_provenance() -> None:
    chunks = chunk_kb()[:5]
    embedded = embed_chunks(chunks)
    assert [e.chunk_id for e in embedded] == [c.chunk_id for c in chunks]
    for e, c in zip(embedded, chunks, strict=True):
        assert isinstance(e, EmbeddedChunk)
        assert e.model == "tapi-hashing-v1"  # proveniência do vetor (embedder offline)
        assert e.dimension == DEFAULT_OFFLINE_DIM
        assert e.chunk.url.startswith("http")  # chunk segue auto-suficiente p/ citar (§8)
        # embeda o contextual_text (breadcrumb + corpo, F3.2), não o `text` puro:
        assert e.vector == HashingEmbedder().embed_query(c.contextual_text)


def test_embed_chunks_empty_is_empty() -> None:
    assert embed_chunks([]) == ()


def test_embed_kb_covers_whole_kb_deterministically() -> None:
    first = embed_kb()
    second = embed_kb()
    assert len(first) == len(chunk_kb())  # um vetor por chunk da KB
    assert [e.chunk_id for e in first] == [e.chunk_id for e in second]  # estável entre runs
    assert all(e.dimension == DEFAULT_OFFLINE_DIM for e in first)


def test_embed_query_helper_uses_default_embedder() -> None:
    assert embed_query("teste") == HashingEmbedder().embed_query("teste")


# --- Backend real degrada limpo offline ------------------------------------------------------


def test_nv_embedqa_degrades_cleanly_without_credentials() -> None:
    # Hook de rede/GPU: sem NVIDIA_API_KEY e sem NIM, levanta EmbedderUnavailable.
    nv = NVEmbedQA(api_key="")
    with pytest.raises(EmbedderUnavailable):
        nv.embed_query("x")
    with pytest.raises(EmbedderUnavailable):
        nv.embed_passages(["x"])


def test_nv_embedqa_uses_configured_model() -> None:
    from packages.config import get_settings

    assert NVEmbedQA().model == get_settings().nv_embed_model
    assert NVEmbedQA(model="custom/embed").model == "custom/embed"
