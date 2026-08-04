"""Faithfulness do briefing (F7.2c) — fidelidade do **texto final** às evidências citadas.

Irmã da classificação (F7.2), do AIMI (F6.4) e da recomendação (F7.2b): aqueles medem
**diagnóstico** e **prescrição**; este mede o **artefato que o gerente lê** — o briefing (F4.4).
O Guardrails (F4.5) só dá um gate **binário** (toda recomendação tem evidência dos dois lados);
falta aferir se a **prosa gerada** (resumo + os três eixos do §2) extrapola as fontes que cita.
F7.2c fecha essa lacuna: aplica a **faithfulness do RAGAS** (frações de afirmações ancoradas nos
contextos) **sobre o briefing**, não só sobre o RAG.

O que é "afirmação" × o que é "fonte" (a distinção que dá sentido à métrica):

- **Afirmações (claims) = os 4 campos que o briefing GERA** — `resumo_executivo`, `acao_comercial`,
  `acao_tecnica`, `acao_comunitaria` (exatamente os `briefing._REFINABLE`, os que o Nemotron-Super
  reescreve quando ligado). O diagnóstico (AIMI) e as recomendações **não** são claims do briefing:
  são entrada **upstream já aterrada** (F2.6/F4.2), que o briefing sintetiza.
- **Fontes (contextos) = o material aterrado de onde a prosa sai** — o bloco AIMI (classe/total +
  cada pilar com score/faixa/justificativa + os snippets de evidência), cada recomendação (tech/
  prioridade/justificativas/próxima-ação + os snippets dos **dois lados**, F4.3) e os **fatos fixos
  do programa NVIDIA Inception** (créditos/`build.nvidia.com`/NIM·NeMo/eventos/comunidade), que o
  eixo comunitário descreve. A métrica então pega o **net-new**: uma afirmação (ROI inventado,
  cliente/funding alegado, maturidade superestimada) que **não** está em nenhuma fonte.

**Por que o default offline beira 1,0 — e é o ponto:** a espinha determinista (`build_briefing`)
só **reafirma** o diagnóstico/recomendações/programa — é fiel **por construção** (anti-alucinação,
o invariante do projeto). O número offline é, portanto, um **guard de regressão** (se alguém fizer
a espinha afirmar algo sem fonte, cai) — e o piso do CI. O número que **importa medir ao vivo** é o
do **`--llm`**: aí o Super reescreve os 4 campos e a fidelidade **pode** degradar — é onde o LLM
**muda o resultado** (≠ F7.2b, em que a *seleção* de techs é determinística e o LLM só refina a
redação sem mudar o veredito). Por isso F7.2c **tem** `--llm` e F7.2b não.

O **scorer é o mesmo** (proxy lexical da faithfulness, determinístico/comparável) nos dois modos —
só o **texto do briefing** troca (espinha × Super refinado), isolando a variável que interessa. A
faithfulness com **juiz LLM** (lib `ragas` + Nemotron) sobre o briefing é a consolidação da **F7.3**
(`RagasJudge`); aqui o backend fica reservado, igual à disciplina do `ragas.py`.

**Fora de escopo (F2.13):** `non-AI` é roteada ao briefing fora-de-escopo (sem recomendação) — o
harness as exclui (in-scope = AI-native + AI-enabled, como na produção e no F7.2b). A consolidação
em `docs/ARQUITETURA.md §9` é da **F7.5**.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from packages.agents import make_briefing
from packages.agents.briefing import _PILLAR_PT, RefineFn, _default_refine
from packages.schemas import AIMIScore, Briefing, Recommendation

from .aimi_correlation import profile_for
from .dataset import LabeledStartup, load_eval_set
from .ragas import faithfulness
from .recommendation_metrics import aimi_from_labels, is_in_scope, recommended_for

#: Gate do briefing (§7 / F7.2c): faithfulness do texto final ≥ 0,80 (meta declarada, revisável).
FAITHFULNESS_THRESHOLD = 0.80

#: Os 4 eixos textuais que o briefing **gera** (e o Super refina) — as afirmações que pontuamos.
#: Espelha `briefing._REFINABLE`; mantido aqui p/ o relatório nomear cada eixo no recorte.
NARRATIVE_FIELDS: tuple[str, ...] = (
    "resumo_executivo",
    "acao_comercial",
    "acao_tecnica",
    "acao_comunitaria",
)

#: Fatos **fixos e verdadeiros** do programa NVIDIA Inception — a fonte do eixo comunitário
#: (`acao_comunitaria`), que descreve a oferta do programa, não evidência por-empresa. Incluí-los
#: como contexto faz a métrica medir **extrapolação** (afirmar algo fora destes fatos), não o
#: reafirmar o que o programa de fato oferece. Cobre os tokens que o gerador determinista usa.
_INCEPTION_PROGRAM = (
    "O NVIDIA Inception oferece onboarding com créditos de GPU e cloud, acesso a NIM e NeMo via "
    "build.nvidia.com, suporte técnico, eventos e comunidade (GTM) para destravar a execução das "
    "tecnologias recomendadas."
)

#: O **framework de decisão** do produto (`docs/ARQUITETURA.md §3.6`) — a
#: fonte do eixo comercial (`acao_comercial`). É conhecimento de domínio **fixo e documentado**, não
#: evidência por-empresa: o briefing **aplica** este framework ao diagnóstico (não o inventa). Como
#: o `_INCEPTION_PROGRAM`, entra no contexto p/ a métrica medir extrapolação **além** do framework —
#: não penalizar o briefing por usar a linguagem canônica do plano `classe × AIMI`.
_DECISION_FRAMING = (
    "Plano de decisão classe × AIMI: empresa AI-native com Data Moat e Workflow Depth altos e "
    "Technical Optimization baixo é o alvo de graduação, o perfil de maior upside para a NVIDIA e "
    "maior prioridade de outreach do Inception. Graduação é a abordagem técnica de internalizar a "
    "inferência, migrando de API externa para stack NVIDIA própria (NIM, TensorRT-LLM, Triton); o "
    "GPU Graduation Engine quantifica o ROI dessa migração. Maturidade alta (AIMI alto) pede "
    "outreach de relacionamento, parceria, distribuição e co-marketing; AIMI baixo pede nutrição e "
    "qualificação do caso de uso antes de uma abordagem comercial mais forte."
)


def briefing_narrative(briefing: Briefing) -> str:
    """Concatena os 4 campos gerados (não-vazios) — a prosa cuja fidelidade se afere."""
    return " ".join(
        text for f in NARRATIVE_FIELDS if (text := getattr(briefing, f))
    )


def _aimi_contexts(aimi: AIMIScore) -> list[str]:
    """Contexto aterrado do diagnóstico: classe/total + pilares (fato/justificativa/snippets)."""
    ctx = [f"Classe {aimi.classificacao.value}; AIMI total {aimi.total}/100."]
    for p in aimi.pillars:
        banda = p.band.value if p.band else "n/d"
        ctx.append(f"{_PILLAR_PT[p.pilar]}: {p.score}/25 ({banda}). {p.justificativa}")
        ctx.extend(ev.snippet for ev in p.evidencia)
    return ctx


def _rec_contexts(rec: Recommendation) -> list[str]:
    """Contexto aterrado de uma recomendação: cabeçalho + justificativas/ação + snippets 2 lados."""
    ctx = [
        f"{rec.tech} — prioridade {rec.prioridade.value}, complexidade {rec.complexidade.value}.",
        rec.justificativa_tecnica,
        rec.justificativa_negocio,
        rec.proxima_acao,
    ]
    ctx.extend(ev.snippet for ev in rec.evidencia_gap)
    ctx.extend(ev.snippet for ev in rec.evidencia_nvidia)
    return ctx


def briefing_contexts(briefing: Briefing) -> list[str]:
    """As fontes aterradas do briefing: diagnóstico + recomendações + fatos do programa Inception.

    É contra esta união que a faithfulness checa cada afirmação da prosa. **Não** inclui os 4 campos
    gerados (isso seria circular): mede o net-new, o que a prosa diz **além** do que as fontes dão.
    """
    ctx: list[str] = [_INCEPTION_PROGRAM, _DECISION_FRAMING]
    if briefing.aimi is not None:
        ctx.extend(_aimi_contexts(briefing.aimi))
    for rec in briefing.recomendacoes:
        ctx.extend(_rec_contexts(rec))
    return ctx


def briefing_faithfulness(briefing: Briefing) -> float:
    """Faithfulness do texto final: fração das frases geradas ancoradas nas fontes (∈[0,1])."""
    return faithfulness(briefing_narrative(briefing), briefing_contexts(briefing))


def briefing_for(entry: LabeledStartup, *, refine: RefineFn | None = None) -> Briefing:
    """Monta o briefing da entrada — AIMI rotulado + recomendações (recall máx) → `make_briefing`.

    Reusa a montagem do F7.2b (`aimi_from_labels` + `recommended_for`, ambos offline e com evidência
    dos dois lados) e o perfil só-de-descrição (`profile_for`/F6.4). `refine=None` ⇒ espinha
    determinista (offline, reproduzível); `refine=<Super>` ⇒ briefing **realmente refinado** (rede).
    """
    aimi = aimi_from_labels(entry)
    recs = recommended_for(entry)
    return make_briefing(aimi, profile_for(entry), recs, empresa=entry.nome, refine=refine)


class EntryFaithfulness(BaseModel):
    """Fidelidade do briefing de uma entrada — a linha rastreável (§8): total + recorte por eixo."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    nome: str
    region: str
    classificacao: str
    n_recs: int = Field(ge=0)
    faithfulness: float = Field(ge=0.0, le=1.0, description="Sobre os 4 campos gerados juntos.")
    per_field: dict[str, float] = Field(description="Faithfulness de cada eixo (onde extrapola).")


class BriefingFaithfulnessReport(BaseModel):
    """Relatório do briefing (F7.2c) — faithfulness média + recorte por eixo; a F7.5 consolida."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend: str = Field(description="lexical-offline (espinha) ou super-refined (texto do --llm).")
    n_in_scope: int = Field(ge=0)
    n_out_of_scope: int = Field(ge=0, description="non-AI (fora de escopo, F2.13) — não avaliadas.")
    mean_faithfulness: float = Field(ge=0.0, le=1.0, description="Média das in-scope (o gate).")
    min_faithfulness: float = Field(ge=0.0, le=1.0, description="Pior entrada (a cauda).")
    per_field_mean: dict[str, float] = Field(description="Média por eixo (§2) — onde desliza.")
    per_entry: tuple[EntryFaithfulness, ...]
    meets_threshold: bool = Field(description=f"mean_faithfulness ≥ {FAITHFULNESS_THRESHOLD} (§7).")


def evaluate_entry(entry: LabeledStartup, *, refine: RefineFn | None = None) -> EntryFaithfulness:
    """Monta o briefing da entrada e mede a faithfulness do texto (total + por eixo)."""
    briefing = briefing_for(entry, refine=refine)
    contexts = briefing_contexts(briefing)
    per_field = {
        f: round(faithfulness(text, contexts), 6)
        for f in NARRATIVE_FIELDS
        if (text := getattr(briefing, f))
    }
    return EntryFaithfulness(
        id=entry.id,
        nome=entry.nome,
        region=entry.region.value,
        classificacao=entry.classificacao.value,
        n_recs=len(briefing.recomendacoes),
        faithfulness=briefing_faithfulness(briefing),
        per_field=per_field,
    )


def evaluate_briefing_faithfulness(
    entries: Sequence[LabeledStartup] | None = None,
    *,
    refine: RefineFn | None = None,
) -> BriefingFaithfulnessReport:
    """Avalia a faithfulness do briefing sobre o eval set (F1.12) — média + recorte por eixo.

    Roda **por entrada in-scope** (AI-native + AI-enabled); `non-AI` (fora de escopo, F2.13) fica à
    parte. Default = espinha determinista (offline, todo o eval set); `refine=<Super>` mede o texto
    **refinado ao vivo** (o que o `--llm` do CLI liga). A média é a métrica do gate; o `min` e o
    recorte por eixo mostram a cauda e **onde** a prosa extrapola.
    """
    entries = tuple(entries) if entries is not None else load_eval_set()
    in_scope = [e for e in entries if is_in_scope(e)]
    n_out = len(entries) - len(in_scope)

    per_entry = tuple(evaluate_entry(e, refine=refine) for e in in_scope)
    scores = [r.faithfulness for r in per_entry]
    mean_f = round(sum(scores) / len(scores), 6) if scores else 0.0
    min_f = round(min(scores), 6) if scores else 0.0

    # Média por eixo só sobre as entradas em que o eixo existe (não-vazio) — comparável e honesto.
    per_field_mean: dict[str, float] = {}
    for f in NARRATIVE_FIELDS:
        vals = [r.per_field[f] for r in per_entry if f in r.per_field]
        per_field_mean[f] = round(sum(vals) / len(vals), 6) if vals else 0.0

    return BriefingFaithfulnessReport(
        backend="super-refined" if refine is not None else "lexical-offline",
        n_in_scope=len(in_scope),
        n_out_of_scope=n_out,
        mean_faithfulness=mean_f,
        min_faithfulness=min_f,
        per_field_mean=per_field_mean,
        per_entry=per_entry,
        meets_threshold=mean_f >= FAITHFULNESS_THRESHOLD,
    )


def _print_report(report: BriefingFaithfulnessReport) -> None:
    mark = "OK " if report.meets_threshold else "XX "
    print(
        f"{mark}Faithfulness do briefing (F7.2c · {report.backend}): "
        f"mean={report.mean_faithfulness} (gate ≥ {FAITHFULNESS_THRESHOLD}; "
        f"min={report.min_faithfulness}; in-scope={report.n_in_scope}, "
        f"fora-de-escopo={report.n_out_of_scope})"
    )
    for f in NARRATIVE_FIELDS:
        print(f"   {f:18} mean={report.per_field_mean[f]:.3f}")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI do briefing (F7.2c): avalia e falha (exit 1) abaixo do gate §7.

    Default = espinha determinista offline (o piso/guard de regressão, sem rede). `--llm` mede o
    briefing **refinado pelo Nemotron-Super real** (faz chamadas à API, gasta créditos) — onde a
    fidelidade pode de fato degradar (o LLM reescreve os 4 campos).
    """
    import argparse

    parser = argparse.ArgumentParser(description="Faithfulness do briefing vs fontes (F7.2c).")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="mede o briefing refinado pelo Nemotron-Super real (rede) em vez da espinha offline.",
    )
    args = parser.parse_args(argv)
    refine: RefineFn | None = (lambda b: _default_refine(b)) if args.llm else None
    report = evaluate_briefing_faithfulness(refine=refine)
    _print_report(report)
    return 0 if report.meets_threshold else 1


__all__ = [
    "FAITHFULNESS_THRESHOLD",
    "NARRATIVE_FIELDS",
    "briefing_narrative",
    "briefing_contexts",
    "briefing_faithfulness",
    "briefing_for",
    "EntryFaithfulness",
    "BriefingFaithfulnessReport",
    "evaluate_entry",
    "evaluate_briefing_faithfulness",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
