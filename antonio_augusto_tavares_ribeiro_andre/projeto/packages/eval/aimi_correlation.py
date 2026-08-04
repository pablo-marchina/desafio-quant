"""Eval do índice AIMI (F6.4) — correlação do AIMI heurístico com os rótulos de F1.12.

Mede o quanto a **heurística v1** (F6.1) recupera o AIMI **rotulado** (ground-truth de
`data/eval/`, F1.12) a partir do **mesmo sinal que a produção tem do lado público**: a
descrição da empresa. Para cada entrada do eval set constrói um `StartupProfile`
**só-de-descrição** (descrição + setor como `Claim`, espelhando o que o `extractor`/F2.5
entrega ao `classifier`), roda `heuristic_score` e correlaciona — por **Spearman**
(rank-based, robusto a sub-predição de escala) — o **total predito** vs o **total
rotulado**. É o harness do índice; a **F7.2 consolida** a métrica e aplica o gate
(Spearman ≥ **0,70** com os rótulos, meta do §7).

Por que Spearman (e não erro absoluto): o ground-truth segue a **definição** da RUBRICA
(F0.11), não a heurística — um perfil só-de-descrição **sub-prediz** a magnitude (sem os
sinais estruturados de funding/clientes/tecnologias que a coleta real traz), mas o que
importa para "o índice ordena as empresas como o rótulo?" é a **ordem**, que o rank captura.

**Honesto sobre o limite (por pilar):** a descrição-só recupera bem os pilares **textuais**
(Data Moat, Workflow Depth e — o que move a graduação — Technical Optimization), mas
**Distribution Moat** correlaciona fraco: seus sinais (rodada de funding, clientes
enterprise) vivem em campos **estruturados** ausentes de uma fixture em prosa. O total
ainda correlaciona forte porque P4 é 1 de 4 pilares. O `spearman_by_pillar` expõe isso por
pilar, sem maquiar. Puro/offline/determinístico — Spearman em **Python puro** (sem
numpy/scipy, que não estão no CI), como a espinha verde do F2–F4.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from packages.agents import heuristic_score
from packages.schemas import AIMIPillar, AIMIScore, Claim, Evidence, PillarScore, StartupProfile
from packages.schemas.enums import Classification

from .dataset import ExpectedPillars, LabeledStartup, load_eval_set

#: Gate do índice (§7 / F7.2): correlação de Spearman do AIMI com os rótulos de F1.12.
SPEARMAN_THRESHOLD = 0.70

#: Evidência sintética do lado-público da fixture (offline determinístico, sem `now()` —
#: igual ao harness do §5.5, F4.8). Ancora a descrição p/ a RUBRICA §0 não travar o pilar.
_EVAL_EV = Evidence(
    url="https://eval.example",
    snippet="perfil sintético do eval set rotulado (F1.12)",
    fetched_at=datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
    content_hash="eval-f64",
)

#: Placeholder p/ reconstruir o `AIMIScore` do `model_aimi` (F7.1): o veredito real já é o score
#: que a heurística deu sobre a evidência raspada COMPLETA na produção — aqui só satisfazemos a
#: RUBRICA §0 (sub-score > 6 exige citação); a fonte real está nos `evidence_urls` da entrada.
_MODEL_EV = Evidence(
    url="https://cohort.eval",
    snippet="AIMI de produção sobre a evidência raspada da coorte (F7.1)",
    fetched_at=datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
    content_hash="eval-cohort",
)
_PILLAR_BY_FIELD = {p.value: p for p in AIMIPillar}


def _aimi_from_pillars(pillars: ExpectedPillars, classificacao: Classification) -> AIMIScore:
    """Reconstrói o `AIMIScore` dos 4 pilares que a produção computou (`model_aimi`, F7.1).

    Para entrada real, o **predito** é o AIMI da heurística sobre a evidência **completa** (F1.14),
    não o re-cálculo sobre a `descricao`-resumo de 1 linha (que afunda no piso). Anexa `_MODEL_EV`
    em todo pilar p/ não esbarrar na RUBRICA §0 (a evidência real vive nos `evidence_urls`).
    """
    pscore = {
        field: PillarScore(
            pilar=_PILLAR_BY_FIELD[field],
            score=getattr(pillars, field),
            justificativa="AIMI de produção sobre a evidência raspada (F7.1).",
            evidencia=[_MODEL_EV],
        )
        for field in ("data_moat", "workflow_depth", "technical_optimization", "distribution_moat")
    }
    return AIMIScore(
        **pscore,
        classificacao=classificacao,
        heuristic_version="v1",  # é o score que a heurística v1 deu na produção (F1.14)
        total=pillars.total,
    )


def profile_for(entry: LabeledStartup) -> StartupProfile:
    """Monta o `StartupProfile` só-de-descrição da entrada — o sinal público que a produção vê.

    Descrição e setor entram como `Claim` ancorado (espelha o `extractor`/F2.5); os campos
    estruturados (tecnologias/clientes/funding) ficam vazios de propósito — a fixture é prosa,
    e é exatamente esse o teto de informação que o harness mede contra o rótulo.
    """
    return StartupProfile(
        nome=entry.nome,
        pais=entry.pais,
        descricao=Claim[str](value=entry.descricao, evidence=[_EVAL_EV]),
        setor=Claim[str](value=entry.setor, evidence=[_EVAL_EV]),
    )


def predicted_aimi(entry: LabeledStartup) -> AIMIScore:
    """AIMI **predito** pela heurística v1 (F6.1).

    Entrada real com `model_aimi` (F7.1): usa o AIMI que a heurística produziu sobre a evidência
    raspada **completa** na produção — a `descricao`-resumo de 1 linha **não** é o sinal que a
    produção vê (sem ela a heurística starva e afunda no piso, falseando a correlação). Fixtures
    sintéticas (prosa rica) seguem rodando a heurística sobre a descrição (que É o sinal).
    """
    if entry.model_aimi is not None:
        return _aimi_from_pillars(entry.model_aimi, entry.classificacao)
    return heuristic_score(profile_for(entry))


def _ranks(values: Sequence[float]) -> list[float]:
    """Postos 1..n com **empates pela média** (fractional ranking), p/ o Spearman tolerar laços."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1  # média dos postos [i+1 .. j+1] (1-based)
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Correlação de **Spearman** (Pearson sobre os postos) — Python puro, com empates.

    Devolve `0.0` quando alguma série é constante (variância nula = correlação indefinida);
    `±1.0` para ordem idêntica/inversa. Levanta se as séries têm tamanhos diferentes ou < 2.
    """
    if len(xs) != len(ys):
        raise ValueError(f"séries de tamanhos diferentes: {len(xs)} != {len(ys)}")
    n = len(xs)
    if n < 2:
        raise ValueError("Spearman exige ao menos 2 pontos.")
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    den = (
        sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)
    ) ** 0.5
    return round(num / den, 6) if den else 0.0


class EntryScore(BaseModel):
    """Predito × rotulado de uma entrada — a linha rastreável da correlação (§8)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    nome: str
    predicted_total: int = Field(ge=0, le=100, description="AIMI total da heurística v1.")
    labeled_total: int = Field(ge=0, le=100, description="AIMI total do ground-truth (F1.12).")


class AIMICorrelationReport(BaseModel):
    """Relatório da correlação do AIMI com os rótulos (F6.4) — a F7.2 consolida em métrica/gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    n: int
    spearman_total: float = Field(ge=-1.0, le=1.0, description="Spearman predito×rotulado (total).")
    spearman_by_pillar: dict[str, float] = Field(
        description="Spearman por pilar (`AIMIPillar.value` → ρ) — diagnóstico, expõe P4 fraco."
    )
    per_entry: tuple[EntryScore, ...]
    meets_threshold: bool = Field(description=f"spearman_total ≥ {SPEARMAN_THRESHOLD} (gate F7.2).")


def evaluate_aimi_correlation(
    entries: Sequence[LabeledStartup] | None = None,
) -> AIMICorrelationReport:
    """Correlaciona o AIMI predito (heurística v1) com os rótulos do eval set (F1.12).

    Roda `heuristic_score` **uma vez** por entrada (perfil só-de-descrição), correlaciona o
    total e cada pilar via Spearman, e agrega o relatório rastreável. Default = todo o eval set.
    """
    entries = tuple(entries) if entries is not None else load_eval_set()
    predicted = [predicted_aimi(e) for e in entries]

    pred_total = [p.total for p in predicted]
    gold_total = [e.aimi.total for e in entries]
    spearman_total = spearman(pred_total, gold_total)

    by_pillar: dict[str, float] = {}
    for pilar in AIMIPillar:
        field = pilar.value  # casa o nome do campo no AIMIScore e em ExpectedPillars
        pred = [getattr(p, field).score for p in predicted]
        gold = [getattr(e.aimi, field) for e in entries]
        by_pillar[field] = spearman(pred, gold)

    per_entry = tuple(
        EntryScore(id=e.id, nome=e.nome, predicted_total=p.total, labeled_total=e.aimi.total)
        for e, p in zip(entries, predicted, strict=True)
    )
    return AIMICorrelationReport(
        n=len(entries),
        spearman_total=spearman_total,
        spearman_by_pillar=by_pillar,
        per_entry=per_entry,
        meets_threshold=spearman_total >= SPEARMAN_THRESHOLD,
    )


def _print_report(report: AIMICorrelationReport) -> None:
    mark = "OK " if report.meets_threshold else "XX "
    print(
        f"{mark}Correlação AIMI×rótulos (F6.4): Spearman(total)={report.spearman_total} "
        f"(gate ≥ {SPEARMAN_THRESHOLD}, n={report.n})"
    )
    for pilar, rho in report.spearman_by_pillar.items():
        print(f"   {pilar:24} ρ={rho:+.4f}")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI da correlação do índice (F6.4): avalia offline e falha (exit 1) abaixo do gate F7.2."""
    report = evaluate_aimi_correlation()
    _print_report(report)
    return 0 if report.meets_threshold else 1


__all__ = [
    "SPEARMAN_THRESHOLD",
    "profile_for",
    "predicted_aimi",
    "spearman",
    "EntryScore",
    "AIMICorrelationReport",
    "evaluate_aimi_correlation",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
