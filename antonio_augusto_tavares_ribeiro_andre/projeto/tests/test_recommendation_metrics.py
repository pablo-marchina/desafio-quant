"""Métricas da recomendação (F7.2b) — precision/recall de techs vs rótulos (F1.12).

Irmão do `test_classification_metrics` (F7.2) e do `test_recommend_cases` (F4.8): mede a
**prescrição** sobre o eval set held-out, não só os 7 casos do brief. Exercita:

1. **Núcleo puro** (`_matches`, `_prf`): casamento de tech tolerante a parentético e a aritmética
   de P/R/F1 — testáveis com casos conhecidos, sem tocar o eval set.
2. **Escopo (F2.13)**: as `non-AI` (fora de escopo) são contadas à parte, não avaliadas.
3. **Invariante dos dois lados (F4.5)**: toda recomendação emitida tem evidência startup + NVIDIA
   → `both_sided_rate == 1,0` (gate duro).
4. **Recall onde importa**: nos **alvos de graduação** (a coorte que o produto existe p/ achar,
   F6.13) o recall das techs esperadas ≥ gate §7 (0,70) — a graduação NIM/TensorRT/Triton sai.
5. **Determinismo** e **caminho LLM**: o adapter de refino (F4.2) não muda *quais* techs → o
   veredito de precision/recall é idêntico com ou sem ele.
"""

from __future__ import annotations

import json

from packages.eval import load_eval_set
from packages.eval.recommendation_metrics import (
    PRF_THRESHOLD,
    RECALL_ALTA_THRESHOLD,
    _matches,
    _prf,
    evaluate_recommendation_metrics,
    is_in_scope,
)
from packages.schemas import Classification


def test_matches_tolerates_parenthetical_and_substring() -> None:
    # Núcleo da tech casa nos dois sentidos de especificidade, ignorando o parentético.
    assert _matches("NVIDIA Riva (ASR)", "NVIDIA Riva (ASR/TTS)")  # esperado mais específico
    assert _matches("Triton", "NVIDIA Triton Inference Server")  # esperado é substring
    assert _matches("NVIDIA NIM", "NVIDIA NIM")
    assert not _matches("NVIDIA NIM", "NeMo Guardrails")
    assert not _matches("", "NVIDIA NIM")  # rótulo vazio não casa nada


def test_prf_math_and_zero_denominator() -> None:
    assert _prf(3, 1, 1) == (0.75, 0.75, 0.75)
    assert _prf(0, 5, 0) == (0.0, 0.0, 0.0)  # só FP → precision 0, recall indefinido → 0
    assert _prf(0, 0, 0) == (0.0, 0.0, 0.0)  # sem nada → 0, não NaN


def test_non_ai_is_out_of_scope() -> None:
    # F2.13: non-AI é fora de escopo (nada a recomendar) — não entra no eval da recomendação.
    report = evaluate_recommendation_metrics()
    n_non_ai = sum(1 for e in load_eval_set() if e.classificacao is Classification.NON_AI)
    assert report.n_out_of_scope == n_non_ai
    assert report.n_in_scope == len(load_eval_set()) - n_non_ai
    assert all(
        is_in_scope(e) for e in load_eval_set() if e.classificacao is not Classification.NON_AI
    )


def test_both_sided_invariant_holds_over_the_eval_set() -> None:
    # F4.5: o nó só emite recomendação com evidência dos dois lados — vale em 100% do eval set.
    report = evaluate_recommendation_metrics()
    assert report.both_sided_rate == 1.0
    assert all(e.both_sided for e in report.per_entry)
    assert report.n_recommendations > 0  # de fato emitiu recomendações (não é vácuo)


def test_graduation_targets_meet_recall_gate() -> None:
    # O coração do produto (F6.13): nos alvos de graduação, o recall das techs esperadas ≥ gate §7.
    report = evaluate_recommendation_metrics()
    alvo = next(m for m in report.per_region if m.region == "alvo_graduacao")
    assert alvo.recall >= PRF_THRESHOLD, f"recall em alvo_graduacao={alvo.recall} < {PRF_THRESHOLD}"


def test_evaluation_is_deterministic() -> None:
    assert evaluate_recommendation_metrics() == evaluate_recommendation_metrics()


def test_llm_refinement_preserves_tech_verdict() -> None:
    # O adapter LLM (F4.2) só refina a redação; quais techs entram (e o veredito P/R/F1) é
    # determinístico — um refino plugado não muda a métrica.
    def _refine(skeletons):
        return json.dumps(
            [{"tech": s.tech, "proxima_acao": "AÇÃO REFINADA PELO MODELO"} for s in skeletons]
        )

    base = evaluate_recommendation_metrics()
    refined = evaluate_recommendation_metrics(recommend=_refine)
    assert (refined.tp, refined.fp, refined.fn) == (base.tp, base.fp, base.fn)
    assert (refined.precision, refined.recall) == (base.precision, base.recall)


# --- priority-aware (F7.7): recall@ALTA + precision tolerante ----------------


def test_recall_alta_in_range_and_gate_consistent() -> None:
    report = evaluate_recommendation_metrics()
    assert 0.0 <= report.recall_alta <= 1.0
    # headline knob-free: gate = recall@ALTA ≥ limiar E dois lados = 1,0
    assert report.meets_alta_gate == (
        report.recall_alta >= RECALL_ALTA_THRESHOLD and report.both_sided_rate == 1.0
    )


def test_alvo_and_wrapper_nail_the_alta_lever() -> None:
    # O coração do produto (F6.13): nos alvos de graduação E nos wrappers, a regra surfa a alavanca
    # que o rótulo marca ALTA → recall@ALTA = 1,0. (maduro/periférico são gap-driven baixos por
    # design — a regra não prescreve enterprise/governança a quem não tem gap.)
    report = evaluate_recommendation_metrics()
    by_region = {m.region: m for m in report.per_region}
    assert by_region["alvo_graduacao"].recall_alta == 1.0
    assert by_region["wrapper"].recall_alta == 1.0


def test_recall_alta_aggregates_and_counts_only_alta_labels() -> None:
    report = evaluate_recommendation_metrics()
    # agregação global == soma das regiões
    assert report.tp_alta == sum(m.tp_alta for m in report.per_region)
    assert report.fn_alta == sum(m.fn_alta for m in report.per_region)
    # TP@ALTA + FN@ALTA = total de techs marcadas ALTA no rótulo das in-scope (nada mais entra)
    expected_alta_total = sum(len(e.expected_alta) for e in report.per_entry)
    assert report.tp_alta + report.fn_alta == expected_alta_total


def test_tolerant_precision_never_penalizes_more_than_presence() -> None:
    # A precision tolerante ignora produzidas BAIXA → o FP tolerante nunca excede o FP de presença
    # (as não-BAIXA são subconjunto das produzidas), e fica em [0,1].
    report = evaluate_recommendation_metrics()
    for e in report.per_entry:
        assert e.fp_tolerant <= e.fp
    assert 0.0 <= report.precision_tolerant <= 1.0


def test_llm_refinement_preserves_priority_verdict() -> None:
    # O refino LLM (F4.2) não muda quais techs nem a prioridade (vêm da regra) → recall@ALTA e
    # precision tolerante idênticos com ou sem ele.
    def _refine(skeletons):
        return json.dumps([{"tech": s.tech, "proxima_acao": "REFINADO"} for s in skeletons])

    base = evaluate_recommendation_metrics()
    refined = evaluate_recommendation_metrics(recommend=_refine)
    assert (refined.recall_alta, refined.precision_tolerant) == (
        base.recall_alta,
        base.precision_tolerant,
    )
