"""Métricas de classificação (F7.2): accuracy + macro-F1 do classifier vs rótulos (F1.12).

Garante (a) o núcleo de métricas em Python puro — accuracy/precision/recall/F1 por classe,
macro-F1 (média não-ponderada, ignora classe ausente) e matriz de confusão — com **casos
conhecidos** calculados à mão; e (b) que o harness roda sobre todo o eval set de forma
rastreável, com o gate (`meets_threshold`) coerente com o macro-F1. Offline/determinístico.

Sobre o **piso offline**: a classe (`_classify_class`) exige Workflow Depth > 8 p/ AI-native, e
o perfil só-de-descrição (espelho da produção do lado público) sub-prediz essa magnitude — o
mesmo limite que o F6.4 documenta p/ o índice. Por isso o teste **não** fixa o número nem exige
o gate verde no caminho heurístico: mede a corretude do harness, não tuna o classificador.
"""

from __future__ import annotations

import pytest

from packages.eval import (
    MACRO_F1_THRESHOLD,
    ClassificationReport,
    accuracy,
    class_prf,
    confusion_matrix,
    evaluate_classification,
    load_eval_set,
    macro_f1,
)
from packages.eval.classification_metrics import main
from packages.schemas.enums import Classification

N = Classification.AI_NATIVE
E = Classification.AI_ENABLED
Z = Classification.NON_AI


# --- núcleo de métricas em Python puro (casos conhecidos) ---------------------


def test_accuracy_perfect_and_partial() -> None:
    assert accuracy([N, E, Z], [N, E, Z]) == 1.0
    # 2 de 4 certos (pos0 e pos2).
    assert accuracy([N, N, N, E], [N, E, N, N]) == 0.5


def test_class_prf_known_value() -> None:
    # gold=[N,N,N,E], pred=[N,E,N,N] → p/ AI-native: tp=2, fp=1, fn=1 → P=R=F1=2/3.
    p, r, f1 = class_prf([N, N, N, E], [N, E, N, N], N)
    assert (p, r) == (round(2 / 3, 6), round(2 / 3, 6))
    assert f1 == round(2 / 3, 6)
    # AI-enabled: nenhuma predição acerta (tp=0) → F1=0.
    assert class_prf([N, N, N, E], [N, E, N, N], E)[2] == 0.0


def test_class_prf_zero_denominator_is_zero_not_undefined() -> None:
    # Classe sem suporte nem predição: 0/0 vira 0.0 explícito.
    assert class_prf([N, N], [N, N], Z) == (0.0, 0.0, 0.0)


def test_macro_f1_perfect_and_ignores_absent_class() -> None:
    # Predição perfeita sobre 2 classes presentes → macro-F1 = 1 (non-AI ausente é ignorada).
    assert macro_f1([N, N, E], [N, N, E]) == 1.0
    # gold=[N,N,N,E], pred=[N,E,N,N]: F1(N)=2/3, F1(E)=0, non-AI ausente → (2/3+0)/2.
    assert macro_f1([N, N, N, E], [N, E, N, N]) == pytest.approx(1 / 3, abs=1e-5)


def test_confusion_matrix_covers_full_taxonomy() -> None:
    cm = confusion_matrix([N, N, N, E], [N, E, N, N])
    # Linhas/colunas das 3 classes, zeros explícitos.
    assert set(cm) == {N.value, E.value, Z.value}
    assert all(set(row) == {N.value, E.value, Z.value} for row in cm.values())
    assert cm[N.value][N.value] == 2
    assert cm[N.value][E.value] == 1
    assert cm[E.value][N.value] == 1
    assert cm[Z.value] == {N.value: 0, E.value: 0, Z.value: 0}


def test_core_metrics_validate_inputs() -> None:
    with pytest.raises(ValueError):
        accuracy([N, E], [N])  # tamanhos diferentes
    with pytest.raises(ValueError):
        accuracy([], [])  # vazio
    with pytest.raises(ValueError):
        macro_f1([], [])  # sem classe com suporte
    with pytest.raises(ValueError):
        confusion_matrix([N], [N, E])  # tamanhos diferentes


# --- harness sobre o eval set rotulado (F1.12) --------------------------------


def test_evaluate_runs_on_full_set_and_is_traceable() -> None:
    report = evaluate_classification()
    es = load_eval_set()
    assert isinstance(report, ClassificationReport)
    assert report.n == len(es)
    # Uma linha por entrada, ids batem (rastreável, §8).
    assert {r.id for r in report.per_entry} == {e.id for e in es}
    assert all(row.correct == (row.gold == row.predicted) for row in report.per_entry)
    # A confusão soma o total; o suporte por classe soma o total.
    assert sum(v for row in report.confusion.values() for v in row.values()) == report.n
    assert sum(m.support for m in report.per_class) == report.n


def test_per_class_covers_the_three_classes() -> None:
    per_class = {m.classificacao for m in evaluate_classification().per_class}
    assert per_class == {N.value, E.value, Z.value}


def test_gate_flag_is_consistent_with_macro_f1() -> None:
    report = evaluate_classification()
    assert 0.0 <= report.macro_f1 <= 1.0
    assert 0.0 <= report.accuracy <= 1.0
    assert report.meets_threshold == (report.macro_f1 >= MACRO_F1_THRESHOLD)


def test_main_exit_matches_gate() -> None:
    # `[]` = sem flags → caminho offline (heurística); o `--llm` (rede) fica fora do CI.
    report = evaluate_classification()
    assert main([]) == (0 if report.meets_threshold else 1)
