"""Métricas da recomendação (F7.2b) — precision/recall de techs NVIDIA vs rótulos (F1.12).

Irmã da classificação (F7.2) e da correlação do AIMI (F6.4): onde aqueles medem o **diagnóstico**
(a classe / o índice), este mede a **prescrição** — o recommender (F4.2/F4.3) recomenda as techs
NVIDIA esperadas por empresa, **além** dos 7 casos canônicos do §5.5 (F4.8)? Fecha a lacuna do
Entregável 4 ter a qualidade aferida só pelos exemplos do brief: mede sobre o eval set **held-out**.

Para cada entrada do eval set (F1.12) o harness:

1. Monta o **AIMI rotulado** (ground-truth de `data/eval/`, **não** o predito) — isola o recommender
   do erro do índice, que o F6.4 mede à parte (mesma disciplina do §5.5: uma dimensão por vez).
2. Monta o perfil só-de-descrição (`profile_for`/F6.4 — o sinal público que a produção vê).
3. Roda o recommender sobre uma **recuperação de recall máximo** (`full_recall_retrieval`/F4.8) —
   isola a *prescrição* (qual tech) do *recall do RAG* (medido à parte: cobertura F3.8, RAGAS F7.3).
4. Compara as techs **produzidas × esperadas** (`expected_nvidia_techs` do rótulo).

**Fora de escopo (F2.13):** uma empresa `non-AI` é roteada pelo `evidence_validator` ao briefing
fora-de-escopo, **pulando** a recomendação — nada a recomendar. O harness as exclui (in-scope =
AI-native + AI-enabled, como na produção) e conta à parte; o roteamento em si é coberto pelos
testes do grafo (F2.13), não aqui.

**Métricas (§7):** **recall** (das techs esperadas, quantas recomendamos), **precision** (das
recomendadas, quantas eram esperadas — pega *super-recomendação*), **F1**, a **taxa dos dois lados**
(F4.5: toda recomendação com evidência startup + NVIDIA — invariante duro, não estatístico) e o
**recorte por região** do plano `classe × AIMI` (RUBRICA §6) p/ ver *onde* acerta. Gate §7:
precision/recall ≥ **0,70**; dois lados = **1,0** (metas declaradas, reportadas com honestidade).

**Priority-aware (F7.7) — reportadas AO LADO da presença, nunca no lugar:** o rótulo passou a marcar
cada tech esperada com **prioridade** (ALTA/MÉDIA/BAIXA, ancorada no gap). Daí: **recall@ALTA**
(headline *knob-free* — das techs ALTA, a alavanca que importa, quantas a regra produz; sem peso nem
limiar de rank) e a **precision tolerante** (diagnóstico — ignora como FP o que a *regra* emitiu como
BAIXA, um "considere também"). A precisão de presença (0,56) **fica visível**: ganha-se leitura, não
se apaga o número honesto. A prioridade do lado produzido vem do `rec` (regra), não do rótulo — a
tolerante **não** é circular.

**Determinístico/offline (sem rede):** a **seleção** de techs do recommender é a espinha de regras
(F4.1); o Nemotron-Super (F4.2) só **refina a redação**, não muda *quais* techs entram. Logo a
precision/recall é a **mesma** online e offline e roda 100% no CI — não há `--llm` a medir aqui (ao
contrário do classificador/F7.2, onde o LLM **muda a predição**). Python puro, como a espinha verde.

A consolidação dos números (classificação F7.2 + AIMI F6.4 + recomendação F7.2b + 7 casos F4.8) num
`docs/ARQUITETURA.md §9` é da **F7.5**.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from packages.agents import make_recommendations
from packages.agents.recommender import RecommendFn
from packages.schemas import (
    MAX_SCORE_WITHOUT_EVIDENCE,
    AIMIPillar,
    AIMIScore,
    Classification,
    Evidence,
    PillarScore,
    Priority,
    Recommendation,
)

from .aimi_correlation import profile_for
from .dataset import LabeledStartup, load_eval_set
from .recommend_cases import full_recall_retrieval

#: Gate da recomendação (§7 / F7.2b): precision **e** recall de techs ≥ 0,70 no eval set (F1.12).
PRF_THRESHOLD = 0.70

#: Gate do headline priority-aware (F7.7): recall das techs **ALTA** (a alavanca que importa) ≥ 0,70.
#: Knob-free — só presença das ALTA esperadas no que a regra produz (sem peso, sem limiar de rank).
RECALL_ALTA_THRESHOLD = 0.70

#: Evidência sintética do lado-público do pilar (offline determinístico, sem `now()` — igual ao
#: harness do §5.5/F4.8 e ao do índice/F6.4). Ancora um pilar forte (> 6) p/ a RUBRICA §0 aceitá-lo.
_LABEL_EV = Evidence(
    url="https://eval.example",
    snippet="perfil sintético do eval set rotulado (F1.12)",
    fetched_at=datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
    content_hash="eval-f72b",
)


def _pillar(pilar: AIMIPillar, score: int) -> PillarScore:
    """`PillarScore` do rótulo — RUBRICA §0: score > 6 carrega evidência; um gap (≤6) não a tem
    (o recommender ancora esse lado no perfil público, como na espinha do F4.2/F4.3)."""
    ev = [_LABEL_EV] if score > MAX_SCORE_WITHOUT_EVIDENCE else []
    return PillarScore(pilar=pilar, score=score, justificativa="rótulo eval (F7.2b)", evidencia=ev)


def aimi_from_labels(entry: LabeledStartup) -> AIMIScore:
    """AIMI **rotulado** (ground-truth) da entrada — os 4 pilares + a classe do rótulo (F1.12).

    É o que alimenta o recommender: usar o rótulo (e não o `predicted_aimi`/F6.4) **isola** a
    qualidade da prescrição do erro do índice — só "dado o diagnóstico certo, prescrevo certo?".
    """
    a = entry.aimi
    return AIMIScore(
        data_moat=_pillar(AIMIPillar.DATA_MOAT, a.data_moat),
        workflow_depth=_pillar(AIMIPillar.WORKFLOW_DEPTH, a.workflow_depth),
        technical_optimization=_pillar(AIMIPillar.TECHNICAL_OPTIMIZATION, a.technical_optimization),
        distribution_moat=_pillar(AIMIPillar.DISTRIBUTION_MOAT, a.distribution_moat),
        classificacao=entry.classificacao,
    )


_PAREN = re.compile(r"\([^)]*\)")


def _normalize(label: str) -> str:
    """Normaliza um rótulo de tech p/ casar: remove o parentético e baixa a caixa.

    Casa o rótulo esperado (mais específico, ex.: `NVIDIA Riva (ASR)`) ao produzido
    (`NVIDIA Riva (ASR/TTS)`) sem ser refém da redação do sufixo — o núcleo da tech é o que importa.
    """
    return _PAREN.sub("", label).strip().casefold()


def _matches(expected: str, produced: str) -> bool:
    """`expected` casa `produced` se o núcleo de um for substring do núcleo do outro.

    Bidirecional p/ tolerar ambos os sentidos de especificidade: `Triton` ⊆ `NVIDIA Triton
    Inference Server` e `NVIDIA Riva` ⊇ `NVIDIA Riva (ASR/TTS)` após normalizar o parentético.
    """
    e, p = _normalize(expected), _normalize(produced)
    return bool(e) and bool(p) and (e in p or p in e)


def recommended_for(
    entry: LabeledStartup, *, recommend: RecommendFn | None = None
) -> list[Recommendation]:
    """Recomendações do recommender p/ a entrada (AIMI rotulado + perfil só-descrição + recall máx).

    `recommend` é o adapter LLM injetável (F4.2); como ele só refina a redação, as **techs** (e a
    evidência dos dois lados) não mudam — o veredito de precision/recall é o mesmo com ou sem ele.
    """
    return make_recommendations(
        aimi_from_labels(entry), profile_for(entry), full_recall_retrieval(), recommend=recommend
    )


def is_in_scope(entry: LabeledStartup) -> bool:
    """In-scope = AI-native ou AI-enabled. `non-AI` é fora de escopo (F2.13): nada a recomendar."""
    return entry.classificacao is not Classification.NON_AI


class EntryRecResult(BaseModel):
    """Produzido × esperado de uma entrada — a linha rastreável da recomendação (§8)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    nome: str
    region: str
    classificacao: str
    expected_techs: tuple[str, ...]
    produced_techs: tuple[str, ...]
    matched_techs: tuple[str, ...] = Field(description="Esperadas que apareceram (TP).")
    missing_techs: tuple[str, ...] = Field(description="Esperadas que faltaram (FN).")
    extra_techs: tuple[str, ...] = Field(description="Produzidas não esperadas (FP).")
    tp: int = Field(ge=0)
    fp: int = Field(ge=0)
    fn: int = Field(ge=0)
    # Priority-aware (F7.7): recall@ALTA usa a prioridade do RÓTULO (a alavanca); a precision
    # tolerante usa a prioridade que a REGRA emitiu em cada rec (independente do rótulo = não circular).
    expected_alta: tuple[str, ...] = Field(default=(), description="Esperadas marcadas ALTA (must-have).")
    matched_alta: tuple[str, ...] = Field(default=(), description="ALTA esperadas que saíram (TP@ALTA).")
    tp_alta: int = Field(default=0, ge=0)
    fn_alta: int = Field(default=0, ge=0)
    tp_tolerant: int = Field(default=0, ge=0, description="Produzidas não-BAIXA que eram esperadas.")
    fp_tolerant: int = Field(
        default=0, ge=0, description="Produzidas não-BAIXA não esperadas (FP tolerante — ignora BAIXA)."
    )
    both_sided: bool = Field(description="Toda recomendação tem evidência dos dois lados (F4.5).")


class RegionMetrics(BaseModel):
    """Precision/recall/F1 de uma região do plano `classe × AIMI` (RUBRICA §6) — o recorte do §8."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    region: str
    n: int = Field(ge=0)
    tp: int = Field(ge=0)
    fp: int = Field(ge=0)
    fn: int = Field(ge=0)
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    f1: float = Field(ge=0.0, le=1.0)
    tp_alta: int = Field(default=0, ge=0)
    fn_alta: int = Field(default=0, ge=0)
    recall_alta: float = Field(default=0.0, ge=0.0, le=1.0, description="Recall das techs ALTA (F7.7).")


class RecommendationMetricsReport(BaseModel):
    """Relatório da recomendação (F7.2b) — precision/recall + dois lados; a F7.5 consolida."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    n_in_scope: int = Field(ge=0)
    n_out_of_scope: int = Field(ge=0, description="non-AI (fora de escopo, F2.13) — não avaliadas.")
    tp: int = Field(ge=0)
    fp: int = Field(ge=0)
    fn: int = Field(ge=0)
    precision: float = Field(ge=0.0, le=1.0, description="Micro: ΣTP / Σ(TP+FP) — presença (baseline).")
    recall: float = Field(ge=0.0, le=1.0, description="Micro: ΣTP / Σ(TP+FN) — presença.")
    f1: float = Field(ge=0.0, le=1.0)
    # Priority-aware (F7.7) — reportadas AO LADO da presença, nunca no lugar dela.
    tp_alta: int = Field(default=0, ge=0)
    fn_alta: int = Field(default=0, ge=0)
    recall_alta: float = Field(
        default=0.0, ge=0.0, le=1.0, description="HEADLINE knob-free: recall das techs ALTA (a alavanca)."
    )
    tp_tolerant: int = Field(default=0, ge=0)
    fp_tolerant: int = Field(default=0, ge=0)
    precision_tolerant: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Diagnóstico: precision ignorando produzidas BAIXA."
    )
    both_sided_rate: float = Field(
        ge=0.0, le=1.0, description="Fração das recomendações com evidência dos dois lados (F4.5)."
    )
    n_recommendations: int = Field(ge=0, description="Total de recomendações emitidas (in-scope).")
    per_region: tuple[RegionMetrics, ...]
    per_entry: tuple[EntryRecResult, ...]
    meets_threshold: bool = Field(
        description=f"presença: precision ≥ {PRF_THRESHOLD} E recall ≥ {PRF_THRESHOLD} E dois lados = 1,0."
    )
    meets_alta_gate: bool = Field(
        default=False, description=f"headline F7.7: recall@ALTA ≥ {RECALL_ALTA_THRESHOLD} E dois lados = 1,0."
    )


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Precision/recall/F1 das contagens. Denominador zero → `0.0` (explícito, comparável)."""
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return round(precision, 6), round(recall, 6), round(f1, 6)


def evaluate_entry(
    entry: LabeledStartup, *, recommend: RecommendFn | None = None
) -> EntryRecResult:
    """Avalia uma entrada: roda o recommender e cruza techs produzidas × esperadas (substring)."""
    recs = recommended_for(entry, recommend=recommend)
    produced = tuple(r.tech for r in recs)
    expected = tuple(entry.expected_nvidia_techs)

    matched = tuple(want for want in expected if any(_matches(want, got) for got in produced))
    missing = tuple(want for want in expected if not any(_matches(want, got) for got in produced))
    extra = tuple(got for got in produced if not any(_matches(want, got) for want in expected))

    # recall@ALTA (F7.7): das techs que o RÓTULO marca ALTA (a alavanca), quantas a regra produziu
    # (presença — knob-free, qualquer prioridade do lado produzido).
    expected_alta = tuple(t.tech for t in entry.expected_techs if t.prioridade is Priority.ALTA)
    matched_alta = tuple(w for w in expected_alta if any(_matches(w, g) for g in produced))

    # precision tolerante (F7.7): ignora como FP o que a REGRA emitiu como BAIXA (um "considere
    # também", não uma prescrição) — a prioridade vem do rec, não do rótulo (não circular).
    produced_non_baixa = tuple(r.tech for r in recs if r.prioridade is not Priority.BAIXA)
    tp_tol = sum(1 for g in produced_non_baixa if any(_matches(w, g) for w in expected))

    both_sided = (not recs) or all(r.evidencia_gap and r.evidencia_nvidia for r in recs)
    return EntryRecResult(
        id=entry.id,
        nome=entry.nome,
        region=entry.region.value,
        classificacao=entry.classificacao.value,
        expected_techs=expected,
        produced_techs=produced,
        matched_techs=matched,
        missing_techs=missing,
        extra_techs=extra,
        tp=len(matched),
        fp=len(extra),
        fn=len(missing),
        expected_alta=expected_alta,
        matched_alta=matched_alta,
        tp_alta=len(matched_alta),
        fn_alta=len(expected_alta) - len(matched_alta),
        tp_tolerant=tp_tol,
        fp_tolerant=len(produced_non_baixa) - tp_tol,
        both_sided=both_sided,
    )


def evaluate_recommendation_metrics(
    entries: Sequence[LabeledStartup] | None = None,
    *,
    recommend: RecommendFn | None = None,
) -> RecommendationMetricsReport:
    """Avalia a recomendação sobre o eval set (F1.12): precision/recall de techs + taxa dos 2 lados.

    Roda o recommender (AIMI rotulado + perfil só-descrição + recall máx) **por entrada in-scope** e
    micro-agrega TP/FP/FN; as `non-AI` (fora de escopo, F2.13) ficam à parte, não são avaliadas.
    Default = todo o eval set; `recommend=` injeta o adapter LLM (não muda o veredito de techs).
    """
    entries = tuple(entries) if entries is not None else load_eval_set()
    in_scope = [e for e in entries if is_in_scope(e)]
    n_out = len(entries) - len(in_scope)

    per_entry = tuple(evaluate_entry(e, recommend=recommend) for e in in_scope)
    tp = sum(r.tp for r in per_entry)
    fp = sum(r.fp for r in per_entry)
    fn = sum(r.fn for r in per_entry)
    precision, recall, f1 = _prf(tp, fp, fn)

    # Priority-aware (F7.7): recall@ALTA (das ALTA esperadas) e precision tolerante (ignora BAIXA).
    tp_alta = sum(r.tp_alta for r in per_entry)
    fn_alta = sum(r.fn_alta for r in per_entry)
    recall_alta = round(tp_alta / (tp_alta + fn_alta), 6) if (tp_alta + fn_alta) else 0.0
    tp_tol = sum(r.tp_tolerant for r in per_entry)
    fp_tol = sum(r.fp_tolerant for r in per_entry)
    precision_tolerant = round(tp_tol / (tp_tol + fp_tol), 6) if (tp_tol + fp_tol) else 0.0

    n_recs = sum(len(r.produced_techs) for r in per_entry)
    both_sided_hits = sum(1 for r in per_entry if r.both_sided)
    both_sided_rate = round(both_sided_hits / len(per_entry), 6) if per_entry else 0.0

    regions = {r.region for r in per_entry}
    per_region = tuple(
        RegionMetrics(
            region=region,
            n=sum(1 for r in per_entry if r.region == region),
            tp=(rtp := sum(r.tp for r in per_entry if r.region == region)),
            fp=(rfp := sum(r.fp for r in per_entry if r.region == region)),
            fn=(rfn := sum(r.fn for r in per_entry if r.region == region)),
            **dict(zip(("precision", "recall", "f1"), _prf(rtp, rfp, rfn), strict=True)),
            tp_alta=(rta := sum(r.tp_alta for r in per_entry if r.region == region)),
            fn_alta=(rfa := sum(r.fn_alta for r in per_entry if r.region == region)),
            recall_alta=(round(rta / (rta + rfa), 6) if (rta + rfa) else 0.0),
        )
        for region in sorted(regions)
    )

    return RecommendationMetricsReport(
        n_in_scope=len(in_scope),
        n_out_of_scope=n_out,
        tp=tp,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        tp_alta=tp_alta,
        fn_alta=fn_alta,
        recall_alta=recall_alta,
        tp_tolerant=tp_tol,
        fp_tolerant=fp_tol,
        precision_tolerant=precision_tolerant,
        both_sided_rate=both_sided_rate,
        n_recommendations=n_recs,
        per_region=per_region,
        per_entry=per_entry,
        meets_threshold=(
            precision >= PRF_THRESHOLD and recall >= PRF_THRESHOLD and both_sided_rate == 1.0
        ),
        meets_alta_gate=(recall_alta >= RECALL_ALTA_THRESHOLD and both_sided_rate == 1.0),
    )


def _print_report(report: RecommendationMetricsReport) -> None:
    mark = "OK " if report.meets_alta_gate else "XX "
    print(
        f"{mark}Recomendação×rótulos (F7.7): HEADLINE recall@ALTA={report.recall_alta} "
        f"(gate ≥ {RECALL_ALTA_THRESHOLD}; dois lados={report.both_sided_rate}); "
        f"precision tolerante={report.precision_tolerant} | presença: P={report.precision} "
        f"R={report.recall} F1={report.f1} (in-scope={report.n_in_scope}, "
        f"fora-de-escopo={report.n_out_of_scope})"
    )
    for m in report.per_region:
        print(
            f"   {m.region:16} n={m.n:2}  recall@ALTA={m.recall_alta:.3f}"
            f"  | presença P={m.precision:.3f} R={m.recall:.3f} F1={m.f1:.3f}"
            f"  (TP={m.tp} FP={m.fp} FN={m.fn})"
        )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI da recomendação (F7.2b): avalia offline e falha (exit 1) abaixo do gate §7.

    Sem `--llm`: a seleção de techs é determinística (F4.1) — o Super só refina a redação, então a
    métrica é idêntica online/offline e roda no CI (diferente do classificador/F7.2).
    """
    import argparse

    parser = argparse.ArgumentParser(description="Métricas de recomendação vs eval set (F7.2b).")
    parser.parse_args(argv)
    report = evaluate_recommendation_metrics()
    _print_report(report)
    return 0 if report.meets_threshold else 1


__all__ = [
    "PRF_THRESHOLD",
    "RECALL_ALTA_THRESHOLD",
    "aimi_from_labels",
    "recommended_for",
    "is_in_scope",
    "EntryRecResult",
    "RegionMetrics",
    "RecommendationMetricsReport",
    "evaluate_entry",
    "evaluate_recommendation_metrics",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
