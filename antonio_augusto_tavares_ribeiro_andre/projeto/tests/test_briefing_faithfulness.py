"""Faithfulness do briefing (F7.2c) — fidelidade do texto final às fontes citadas.

Irmão do `test_recommendation_metrics` (F7.2b) e do `test_classification_metrics` (F7.2): mede o
**artefato que o gerente lê** (o briefing/F4.4), não só o diagnóstico/prescrição. Exercita:

1. **Espinha fiel por construção**: o briefing determinista só reafirma diagnóstico/recomendações/
   programa → faithfulness alta (≥ gate §7) e `meets_threshold`. É o piso/guard de regressão do CI.
2. **Sem circularidade**: os 4 campos gerados **não** entram no próprio contexto (senão tudo casaria
   trivialmente) — a métrica mede o *net-new* além das fontes.
3. **Escopo (F2.13)**: as `non-AI` (fora de escopo) ficam à parte, não avaliadas.
4. **A métrica pega o LLM extrapolando**: um refino (F4.2/F4.4) que injeta uma afirmação **sem
   fonte** (clientes/funding inventados) **derruba** a faithfulness; um refino fiel a preserva —
   exatamente onde o `--llm` importa (o LLM **muda** o texto, ≠ F7.2b). Tudo com adapter fake.
5. **Determinismo**: sem `now()`/rede → relatório idêntico entre execuções.
"""

from __future__ import annotations

import json

from packages.eval import load_eval_set
from packages.eval.briefing_faithfulness import (
    FAITHFULNESS_THRESHOLD,
    NARRATIVE_FIELDS,
    briefing_contexts,
    briefing_faithfulness,
    briefing_for,
    briefing_narrative,
    evaluate_briefing_faithfulness,
)
from packages.schemas import Briefing, Classification


def _grad_entry():
    """Uma entrada AI-native com Technical Optimization baixo (gap de inferência), se houver;
    senão a primeira in-scope — só precisa de um briefing com recomendações e os três eixos."""
    for e in load_eval_set():
        if (
            e.classificacao is Classification.AI_NATIVE
            and e.aimi.technical_optimization <= 6
        ):
            return e
    return next(e for e in load_eval_set() if e.classificacao is not Classification.NON_AI)


def _echo_refine(briefing: Briefing) -> str:
    """Refino **fiel**: devolve os 4 campos sem mudar (não extrapola) → faithfulness preservada."""
    return json.dumps({f: getattr(briefing, f) for f in NARRATIVE_FIELDS})


def _hallucinating_refine(briefing: Briefing) -> str:
    """Refino que **extrapola**: injeta no resumo uma afirmação sem nenhuma fonte (anti-padrão)."""
    return json.dumps(
        {
            "resumo_executivo": (
                "A empresa tem 500 clientes enterprise pagantes e captou 50 milhoes de dolares "
                "numa series B liderada por um fundo soberano asiatico no ultimo trimestre."
            )
        }
    )


def test_offline_spine_is_faithful_by_construction() -> None:
    # A espinha determinista só reafirma fontes aterradas → alta faithfulness (piso do CI).
    report = evaluate_briefing_faithfulness()
    assert report.backend == "lexical-offline"
    assert report.n_in_scope > 0
    assert report.meets_threshold
    assert report.mean_faithfulness >= FAITHFULNESS_THRESHOLD
    assert 0.0 <= report.min_faithfulness <= report.mean_faithfulness <= 1.0


def test_non_ai_is_out_of_scope() -> None:
    # F2.13: non-AI não gera recomendação → fora do eval de faithfulness do briefing (igual F7.2b).
    report = evaluate_briefing_faithfulness()
    n_non_ai = sum(1 for e in load_eval_set() if e.classificacao is Classification.NON_AI)
    assert report.n_out_of_scope == n_non_ai
    assert report.n_in_scope == len(load_eval_set()) - n_non_ai


def test_narrative_is_only_the_generated_fields() -> None:
    # A prosa pontuada são só os 4 campos que o briefing gera (o que o Super refina), nada mais.
    briefing = briefing_for(_grad_entry())
    expected = " ".join(t for f in NARRATIVE_FIELDS if (t := getattr(briefing, f)))
    assert briefing_narrative(briefing) == expected
    assert briefing.resumo_executivo in briefing_narrative(briefing)


def test_contexts_exclude_generated_fields_no_circularity() -> None:
    # As fontes não incluem os campos gerados (senão casaria trivialmente); incluem o aterramento.
    briefing = briefing_for(_grad_entry())
    contexts = briefing_contexts(briefing)
    joined = "\n".join(contexts)
    for f in NARRATIVE_FIELDS:
        text = getattr(briefing, f)
        if text:
            assert text not in joined  # nenhum campo gerado vaza p/ o próprio contexto
    # O aterramento está lá: a justificativa de um pilar do AIMI e um snippet de recomendação.
    assert briefing.aimi is not None
    assert any(briefing.aimi.data_moat.justificativa in c for c in contexts)
    assert briefing.recomendacoes  # entrada de graduação recomenda techs
    a_snippet = briefing.recomendacoes[0].evidencia_nvidia[0].snippet
    assert any(a_snippet in c for c in contexts)


def test_per_field_breakdown_covers_all_axes() -> None:
    report = evaluate_briefing_faithfulness()
    assert set(report.per_field_mean) == set(NARRATIVE_FIELDS)
    assert all(0.0 <= v <= 1.0 for v in report.per_field_mean.values())


def test_hallucinated_refinement_lowers_faithfulness() -> None:
    # O ponto do --llm: se o LLM afirma algo sem fonte, a faithfulness cai (vs a espinha offline).
    base = evaluate_briefing_faithfulness()
    bad = evaluate_briefing_faithfulness(refine=_hallucinating_refine)
    assert bad.backend == "super-refined"
    assert bad.per_field_mean["resumo_executivo"] < base.per_field_mean["resumo_executivo"]
    assert bad.mean_faithfulness < base.mean_faithfulness


def test_faithful_refinement_preserves_faithfulness() -> None:
    # Refino que não extrapola (mesmo texto) → métrica idêntica à espinha (só muda o label).
    base = evaluate_briefing_faithfulness()
    echo = evaluate_briefing_faithfulness(refine=_echo_refine)
    assert echo.backend == "super-refined"
    assert echo.mean_faithfulness == base.mean_faithfulness
    assert echo.per_field_mean == base.per_field_mean


def test_single_briefing_faithfulness_in_range() -> None:
    # A métrica por-briefing é um escalar em [0,1] e a espinha de um alvo de graduação é alta.
    score = briefing_faithfulness(briefing_for(_grad_entry()))
    assert 0.0 <= score <= 1.0
    assert score >= FAITHFULNESS_THRESHOLD


def test_determinism() -> None:
    # Sem now()/rede: dois runs offline são byte-a-byte iguais (modelos frozen) — baseline estável.
    assert evaluate_briefing_faithfulness() == evaluate_briefing_faithfulness()
