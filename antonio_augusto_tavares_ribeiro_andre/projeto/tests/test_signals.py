"""Testes da taxonomia de sinais AI-native (F1.11).

Tudo offline/puro (regex sobre texto), como o `_parse` da busca (F1.1). Cobre: o
scan por categoria, a regra de score (peso por categoria, sem inflar com repetição),
a ausência de falso-positivo em tokens curtos ambíguos (`ia`/`ai`), o pré-filtro de
`SearchResult` e o enviesamento de query.
"""

from __future__ import annotations

import pytest

from packages.schemas.enums import AIMIPillar
from packages.scraping import SearchResult, bias_query, prefilter, scan
from packages.scraping.signals import (
    AI_CANDIDATE_MIN_SCORE,
    BIAS_TERMS,
    CATEGORY_PILLAR,
    CATEGORY_WEIGHT,
    STRONG_CANDIDATE_MIN_SCORE,
    TAXONOMY,
)


def _sr(
    title: str, snippet: str, *, url: str = "https://x.example", score: float = 0.5
) -> SearchResult:
    return SearchResult(url=url, title=title, snippet=snippet, score=score)


# --- taxonomia / consistência das tabelas -------------------------------------


def test_tables_share_the_same_categories() -> None:
    cats = set(TAXONOMY)
    assert cats == set(CATEGORY_WEIGHT) == set(CATEGORY_PILLAR)
    assert all(w >= 1 for w in CATEGORY_WEIGHT.values())
    assert all(isinstance(p, AIMIPillar) for p in CATEGORY_PILLAR.values())
    assert STRONG_CANDIDATE_MIN_SCORE > AI_CANDIDATE_MIN_SCORE


# --- scan por categoria -------------------------------------------------------


def test_scan_model_ai_keywords() -> None:
    s = scan("Plataforma de agentes de IA com RAG e LLM para atendimento")
    assert s.categories == {"model_ai"}
    assert s.score == CATEGORY_WEIGHT["model_ai"]
    assert s.is_ai_candidate and not s.is_strong


def test_scan_public_stack() -> None:
    s = scan("Nossa stack: PyTorch, Hugging Face e deploy com vLLM na NVIDIA")
    assert "public_stack" in s.categories
    assert s.score >= CATEGORY_WEIGHT["public_stack"]


def test_scan_ml_hiring_only() -> None:
    # Cargos sem o termo "machine learning" → categoria única ml_hiring.
    s = scan("Vaga: AI Engineer e Data Scientist (MLOps)")
    assert s.categories == {"ml_hiring"}
    assert s.score == CATEGORY_WEIGHT["ml_hiring"]


def test_scan_research() -> None:
    s = scan("Publicamos no arXiv e apresentamos no NeurIPS")
    assert s.categories == {"research"}


def test_scan_multi_category_is_strong() -> None:
    s = scan(
        "Plataforma de IA generativa (LLM/RAG). Vaga: Machine Learning Engineer. Stack em PyTorch."
    )
    assert {"model_ai", "ml_hiring", "public_stack"} <= s.categories
    assert s.is_strong  # várias categorias técnicas → sinal forte


def test_scan_dedups_repeated_term() -> None:
    s = scan("RAG RAG rag")
    rag = [sig for sig in s.signals if sig.term == "rag"]
    assert len(rag) == 1  # conta uma vez
    assert rag[0].matched == "RAG"  # preserva o casing da 1ª ocorrência


def test_scan_empty_text() -> None:
    s = scan("")
    assert s.signals == () and s.score == 0 and not s.is_ai_candidate


# --- ausência de falso-positivo ----------------------------------------------


def test_no_false_positive_on_non_ai_text() -> None:
    s = scan("Padaria artesanal em São Paulo: pães, bolos e cafés especiais")
    assert s.score == 0 and not s.is_ai_candidate


def test_short_ambiguous_tokens_not_matched() -> None:
    # 'ia'/'ai' soltos (em "vai", "pai") não são sinal — ficam fora do léxico.
    s = scan("A empresa vai crescer e o pai do fundador reinvestiu o lucro")
    assert s.score == 0


# --- pré-filtro de candidatas (F1.1 → F2.6) -----------------------------------


def test_prefilter_keeps_ai_drops_non_ai_and_orders_by_score() -> None:
    ai_weak = _sr("Plataforma de IA generativa", "agentes com RAG e LLM", url="https://a.example")
    non_ai = _sr("Padaria artesanal", "pães e bolos", url="https://b.example")
    ai_strong = _sr("Vagas", "Machine Learning Engineer; stack PyTorch", url="https://c.example")

    kept = prefilter([ai_weak, non_ai, ai_strong])
    urls = [r.url for r in kept]
    assert "https://b.example" not in urls  # non-AI descartada
    assert urls == ["https://c.example", "https://a.example"]  # forte antes do fraco


def test_prefilter_strong_threshold() -> None:
    ai_weak = _sr("IA generativa", "RAG e LLM", url="https://a.example")
    ai_strong = _sr("Vagas", "Machine Learning Engineer; stack PyTorch", url="https://c.example")
    kept = prefilter([ai_weak, ai_strong], min_score=STRONG_CANDIDATE_MIN_SCORE)
    assert [r.url for r in kept] == ["https://c.example"]


# --- enviesamento de query (F2.3) --------------------------------------------


def test_bias_query_prepends_original_and_appends_terms() -> None:
    out = bias_query("fintech São Paulo")
    assert out[0] == "fintech São Paulo"  # cobertura geral preservada
    assert len(out) == 1 + min(4, len(BIAS_TERMS))
    assert "fintech São Paulo inteligência artificial" in out


def test_bias_query_limit_zero_returns_only_base() -> None:
    assert bias_query("varejo", limit=0) == ("varejo",)


def test_bias_query_rejects_empty() -> None:
    with pytest.raises(ValueError):
        bias_query("   ")
