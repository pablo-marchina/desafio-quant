"""Comparativo de reranker (F7.4) — NeMo × Cohere × lexical (qualidade/latência/custo).

Tudo offline (espinha verde): o default mede só o `LexicalReranker` (piso, sem rede); os backends
de rede entram por injeção e **degradam limpo** (linha `available=False`) sem credencial/dep — o
comparativo nunca inventa número. Exercita:

1. **Baseline offline**: a linha lexical sai disponível, com qualidade/latência/custo preenchidos.
2. **Degradação limpa**: um backend de rede sem credencial vira uma linha indisponível com o motivo
   (não derruba o relatório nem mente um número).
3. **Decisão por dados**: `best_quality_provider` é o de maior qualidade **entre os disponíveis**.
4. **Tabela de custo**: as três taxas de referência (Cohere paga > NeMo/lexical = 0).
"""

from __future__ import annotations

from packages.eval.ragas import load_rag_questions
from packages.eval.reranker_comparison import (
    COST_PER_1K_QUERIES_USD,
    compare_rerankers,
    measure_reranker,
)
from packages.rag import LexicalReranker, NeMoReranker, build_retriever


def test_offline_comparison_has_lexical_baseline() -> None:
    report = compare_rerankers()  # default offline-safe: só o lexical
    assert report.n_questions == len(load_rag_questions())
    assert len(report.rows) == 1
    row = report.rows[0]
    assert row.provider == "lexical-offline" and row.available
    assert row.faithfulness == 1.0  # resposta extrativa → fiel por construção
    assert 0.0 <= row.quality_mean <= 1.0 and row.quality_mean > 0.7
    assert row.latency_ms_per_query is not None and row.latency_ms_per_query >= 0.0
    assert row.cost_per_1k_queries_usd == 0.0  # offline, sem API
    assert report.best_quality_provider == "lexical-offline"


def test_network_backend_without_credentials_degrades_to_a_row() -> None:
    # NeMo sem chave → linha indisponível (degradou limpo), não exceção; lexical segue disponível.
    rerankers = {"lexical-offline": LexicalReranker(), "nv-rerankqa": NeMoReranker(api_key="")}
    report = compare_rerankers(rerankers)
    by_provider = {r.provider: r for r in report.rows}
    assert by_provider["lexical-offline"].available
    nemo = by_provider["nv-rerankqa"]
    assert not nemo.available
    assert nemo.note  # carrega o motivo da degradação
    assert nemo.quality_mean is None and nemo.latency_ms_per_query is None
    assert nemo.cost_per_1k_queries_usd == 0.0  # custo da tabela ainda é reportado
    # decisão: o vencedor de qualidade é o único disponível.
    assert report.best_quality_provider == "lexical-offline"


def test_measure_reranker_on_lexical_is_available_and_complete() -> None:
    retriever = build_retriever()
    questions = load_rag_questions()
    row = measure_reranker(LexicalReranker(), retriever=retriever, questions=questions)
    assert row.available and row.provider == "lexical-offline"
    assert row.faithfulness is not None and row.quality_mean is not None
    assert row.context_precision is not None and row.context_recall is not None


def test_cost_table_has_the_three_providers() -> None:
    assert set(COST_PER_1K_QUERIES_USD) == {"lexical-offline", "nv-rerankqa", "cohere-rerank"}
    # Cohere é pago (preço público); NeMo no build e o lexical offline não custam por consulta.
    assert COST_PER_1K_QUERIES_USD["cohere-rerank"] > 0.0
    assert COST_PER_1K_QUERIES_USD["nv-rerankqa"] == 0.0
    assert COST_PER_1K_QUERIES_USD["lexical-offline"] == 0.0
