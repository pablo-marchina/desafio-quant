"""Eval do índice AIMI (F6.4): correlação do AIMI heurístico com os rótulos de F1.12.

Garante (a) que o Spearman em Python puro está correto (identidade/inversa, valor conhecido,
empates, séries constantes, validação), e (b) que a heurística v1 (F6.1) **recupera a ordem**
dos rótulos do eval set acima do gate do §7 (Spearman ≥ 0,70 com os rótulos, consolidado na
F7.2). Documenta também o limite honesto: P3 (que move a graduação) é recuperado bem, mas
Distribution Moat é o pilar mais fraco — seus sinais (funding/clientes enterprise) não vivem
numa fixture em prosa. Offline/determinístico, como o resto do harness de eval.
"""

from __future__ import annotations

import pytest

from packages.eval import (
    SPEARMAN_THRESHOLD,
    AIMICorrelationReport,
    evaluate_aimi_correlation,
    load_eval_set,
    predicted_aimi,
    spearman,
)
from packages.eval.aimi_correlation import main

# --- Spearman em Python puro --------------------------------------------------


def test_spearman_identity_and_reverse() -> None:
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert spearman(xs, xs) == 1.0
    assert spearman(xs, list(reversed(xs))) == -1.0


def test_spearman_known_value() -> None:
    # xs e ys com 2 pares trocados → Pearson sobre os postos = 0,6 (conta à mão).
    assert spearman([1, 2, 3, 4], [2, 1, 4, 3]) == 0.6


def test_spearman_is_rank_based_not_scale_based() -> None:
    # Transformação monotônica (não-linear) preserva a ordem → Spearman = 1 (Pearson não seria).
    xs = [1, 2, 3, 4, 5]
    ys = [v**3 for v in xs]
    assert spearman(xs, ys) == 1.0


def test_spearman_handles_ties_and_constant() -> None:
    # Empates: postos pela média, resultado finito em [-1, 1].
    rho = spearman([1, 1, 2, 3], [1, 2, 3, 4])
    assert -1.0 <= rho <= 1.0
    # Série constante (variância nula) → correlação indefinida, devolvida como 0,0.
    assert spearman([5, 5, 5], [1, 2, 3]) == 0.0


def test_spearman_validates_inputs() -> None:
    with pytest.raises(ValueError):
        spearman([1, 2, 3], [1, 2])  # tamanhos diferentes
    with pytest.raises(ValueError):
        spearman([1], [1])  # < 2 pontos


# --- correlação do índice com os rótulos (o gate do §7 / F7.2) -----------------


def test_correlation_meets_threshold() -> None:
    report = evaluate_aimi_correlation()
    assert isinstance(report, AIMICorrelationReport)
    assert report.n == len(load_eval_set())
    assert report.spearman_total >= SPEARMAN_THRESHOLD  # gate F7.2 (≥ 0,70); de fato ~0,82
    assert report.meets_threshold is True


def test_technical_optimization_is_recovered_well() -> None:
    # P3 é o pilar que dispara a graduação (F6.3) — o harness precisa recuperá-lo bem.
    report = evaluate_aimi_correlation()
    assert report.spearman_by_pillar["technical_optimization"] >= SPEARMAN_THRESHOLD


def test_distribution_is_the_weakest_pillar() -> None:
    # Limite honesto: P4 (funding/clientes enterprise) não está numa fixture em prosa →
    # é o pilar de menor correlação. O total ainda passa porque P4 é 1 de 4.
    by_pillar = evaluate_aimi_correlation().spearman_by_pillar
    assert min(by_pillar, key=by_pillar.__getitem__) == "distribution_moat"


def test_per_entry_is_complete_and_traceable() -> None:
    report = evaluate_aimi_correlation()
    es = load_eval_set()
    assert len(report.per_entry) == len(es)
    assert {r.id for r in report.per_entry} == {e.id for e in es}
    for row in report.per_entry:
        assert 0 <= row.predicted_total <= 100
        assert 0 <= row.labeled_total <= 100


def test_predicted_aimi_is_v1_and_deterministic() -> None:
    entry = load_eval_set()[0]
    first = predicted_aimi(entry)
    assert first.heuristic_version == "v1"  # heurística refinada de F6.1
    assert predicted_aimi(entry).total == first.total  # puro/reprodutível


def test_predicted_aimi_uses_model_aimi_for_real_entries() -> None:
    # F7.1 lever: empresa real carrega o AIMI que a heurística deu sobre a evidência COMPLETA
    # (model_aimi). A descrição-resumo de 1 linha afundaria no piso — o predito deve ser o
    # model_aimi, não o re-cálculo sobre a descrição pobre.
    from packages.eval.dataset import ExpectedPillars, LabeledStartup
    from packages.schemas.enums import Classification, PlaneRegion

    rich = ExpectedPillars(
        data_moat=15, workflow_depth=9, technical_optimization=6, distribution_moat=15
    )
    entry = LabeledStartup(
        id="real-x",
        nome="X",
        setor="tech",
        descricao="Empresa de IA.",  # 1 linha pobre → heurística afundaria no piso
        classificacao=Classification.AI_NATIVE,
        region=PlaneRegion.ALVO_GRADUACAO,
        aimi=rich,
        model_aimi=rich,
        synthetic=False,
        label_source="human",
        rationale="teste",
        evidence_urls=["https://x.co"],
    )
    pred = predicted_aimi(entry)
    assert pred.total == rich.total  # usou o model_aimi (45), não o piso da descrição
    assert pred.data_moat.score == 15 and pred.distribution_moat.score == 15
    # sem model_aimi (fixture sintética) cai no heurístico sobre a descrição (piso baixo).
    syn = LabeledStartup(
        id="syn-x",
        nome="X",
        setor="tech",
        descricao="Empresa de IA.",
        classificacao=Classification.AI_NATIVE,
        region=PlaneRegion.ALVO_GRADUACAO,
        aimi=rich,
        rationale="teste",
        synthetic=True,
    )
    assert predicted_aimi(syn).total < rich.total  # descrição-só não alcança o model_aimi


def test_main_returns_zero_when_above_gate() -> None:
    assert main() == 0
