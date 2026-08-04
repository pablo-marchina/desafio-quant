"""Aderência ao §5.5 (F4.8) — o recommender produz o esperado nos 7 exemplos do brief.

Ponta-a-ponta dos 7 exemplos do §5.5 (a `test_recommend_rules.py` cobre 5 no nível de regra/F4.1;
aqui é o nó recommender inteiro sobre todos os 7, via o harness reusável de `packages/eval`). Tudo
offline/determinista: o harness roda o recommender sobre uma recuperação de recall máximo (citação
para toda tech recomendável da KB) — isola a aderência da prescrição (F4.1) e o invariante dos dois
lados (F4.5) do recall do RAG (medido à parte: cobertura F3.8, RAGAS F7.3). Exercita:

1. **Cada caso adere** (parametrizado): as techs esperadas do §5.5 aparecem, com evidência dos dois
   lados em cada recomendação.
2. **Relatório agregado**: os 7 casos passam → `adherence == 1.0` (o que a F7.2 consolida).
3. **Integridade dos casos**: cobrem exatamente os 7 exemplos do §5.5; determinismo.
4. **Caminho LLM**: refinar a redação (adapter injetado) preserva a aderência e os dois lados.
"""

from __future__ import annotations

import json

import pytest

from packages.eval import (
    SECTION_55_CASES,
    RecommendationCase,
    evaluate_recommendation_cases,
    run_case,
)

#: Os 7 exemplos canônicos do §5.5 (a F4.8 enumera estes ids) — guarda contra perder/duplicar caso.
_EXPECTED_CASE_IDS = {
    "voz",
    "dados_tabulares",
    "saude",
    "atendimento_api",
    "robotica",
    "latencia",
    "governanca",
}


@pytest.mark.parametrize("case", SECTION_55_CASES, ids=lambda c: c.id)
def test_case_adheres_to_section_55(case: RecommendationCase) -> None:
    # O recommender produz todas as techs esperadas do §5.5, com evidência dos dois lados (F4.5).
    result = run_case(case)
    assert not result.missing_techs, (
        f"{case.id}: faltaram {list(result.missing_techs)}; "
        f"produzidas={list(result.produced_techs)}"
    )
    assert result.both_sided, f"{case.id}: recomendação sem evidência dos dois lados"
    assert result.passed


def test_report_full_adherence_over_the_seven_examples() -> None:
    # DoD F4 / consolidação F7.2: os 7 casos do §5.5 aderem → adherence 1.0.
    report = evaluate_recommendation_cases()
    assert report.n_cases == 7
    assert report.n_passed == 7
    assert report.adherence == 1.0
    assert all(r.passed for r in report.per_case)


def test_cases_cover_exactly_the_seven_section_55_examples() -> None:
    ids = [c.id for c in SECTION_55_CASES]
    assert len(ids) == len(set(ids))  # sem duplicado
    assert set(ids) == _EXPECTED_CASE_IDS


def test_every_case_declares_expected_techs() -> None:
    # Um caso sem techs esperadas passaria vacuamente — o ground-truth tem de afirmar algo.
    for case in SECTION_55_CASES:
        assert case.expected_techs, f"{case.id}: caso §5.5 sem techs esperadas"


def test_evaluation_is_deterministic() -> None:
    assert evaluate_recommendation_cases() == evaluate_recommendation_cases()


def test_llm_refinement_preserves_adherence() -> None:
    # O adapter LLM (F4.2) só refina a redação; a aderência (quais techs) e os dois lados são
    # deterministas, então um refino plugado não muda o veredito de aderência.
    def _refine(skeletons):
        return json.dumps(
            [{"tech": s.tech, "proxima_acao": "AÇÃO REFINADA PELO MODELO"} for s in skeletons]
        )

    report = evaluate_recommendation_cases(recommend=_refine)
    assert report.n_passed == report.n_cases == 7
