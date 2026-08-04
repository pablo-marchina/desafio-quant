"""Nó **briefing** (F4.4): perfil + AIMI + recomendações → relatório executivo PT-BR (JSON + MD).

Décimo e **último** nó do grafo (ARQUITETURA §3), depois do `human_review` (F2.8). É a saída de
produto do TAPI: o **relatório executivo** que o gerente de Startups & VCs do NVIDIA Inception lê.
Sintetiza o diagnóstico (perfil + AIMI, F2.5/F2.6) e a prescrição (recomendações, F4.2/F4.3) num
`Briefing` (schema F0.5) **em PT-BR** (F0.13), com as próximas-ações nos **três eixos do §2**:

- **`acao_comercial`** — abordagem/timing de outreach (deriva da classe §5.1 + o gap que define a
  região do plano `classe × AIMI`: alvo de graduação tem o maior upside → prioridade);
- **`acao_tecnica`** — adoção da tecnologia, ancorada na **recomendação de maior prioridade**
  (a `proxima_acao` que já vem do recommender, F4.3) + o roadmap das demais;
- **`acao_comunitaria`** — onboarding/créditos/eventos/comunidade do Inception, atado às
  recomendações (os créditos destravam justamente as techs prescritas).

**Decisão de design (espinha verde, igual classifier/F2.6 e recommender/F4.2):** o caminho
**determinista/offline é o default** — o briefing é montado a partir do estado (diagnóstico +
recomendações, ambos já com evidência) sem rede/LLM/GPU (runs reprodutíveis). A peça LLM
(Nemotron-Super, reasoning ON — `briefing@v1`, F0.12) é **plugável** atrás de
`settings.briefing_use_llm` (+ chave) **ou** de um adapter `refine=` injetado, e **refina só a
redação** (resumo + os três eixos), caindo de volta na espinha a qualquer falha. O **diagnóstico e
as recomendações nunca vêm do LLM** — são sempre os do estado, já aterrados em evidência dos dois
lados (anti-alucinação; o invariante que o NeMo Guardrails/F4.5 reforça aqui).

**JSON + Markdown (F4.4):** o contrato `Briefing` é o JSON; `render_markdown` é a **view** PT-BR
derivada do mesmo objeto — render determinístico garante JSON↔Markdown coerentes (o PDF da F4.6 e o
front da F5 consomem daqui). As **variantes terminais** (F2.12 dados insuficientes / F2.13 fora de
escopo) seguem em `terminals.py`; este nó despacha para elas por status e cobre o **caminho normal**
(diagnóstico + recomendação). Sem `aimi` (espinha offline sem classificação) o nó é um **no-op
limpo** (só fecha o run) — grafo verde ponta a ponta (M2/DoD) sem alucinar um relatório sem base.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from packages.config import get_settings
from packages.schemas import (
    AIMIPillar,
    AIMIScore,
    Briefing,
    BriefingStatus,
    Priority,
    Recommendation,
    ROIEstimate,
    RunStatus,
    StartupProfile,
)

from .guardrails import GuardFn, guard_recommendations
from .inception import inception_priority
from .nvidia_rag import gap_pillars
from .terminals import insufficient_data_briefing, out_of_scope_briefing

if TYPE_CHECKING:
    from packages.schemas import GraphState

# Adapter de refino injetável: briefing-esqueleto -> JSON cru do modelo. Default = Nemotron-Super.
RefineFn = Callable[[Briefing], str]

#: Rótulos PT-BR dos pilares do AIMI (RUBRICA/F0.11) para o texto do briefing (produto, F0.13).
_PILLAR_PT: dict[AIMIPillar, str] = {
    AIMIPillar.DATA_MOAT: "Data Moat (dado proprietário)",
    AIMIPillar.WORKFLOW_DEPTH: "Workflow Depth (profundidade de automação)",
    AIMIPillar.TECHNICAL_OPTIMIZATION: "Technical Optimization (stack de inferência própria)",
    AIMIPillar.DISTRIBUTION_MOAT: "Distribution & Moat (distribuição/defensabilidade)",
}

#: Ordem de prioridade p/ ordenar as recomendações no texto/roadmap (alta → média → baixa).
_PRIORITY_RANK: dict[Priority, int] = {Priority.ALTA: 0, Priority.MEDIA: 1, Priority.BAIXA: 2}


# ----------------------------------------------------------------- espinha determinista (texto)


def _by_priority(recs: Sequence[Recommendation]) -> list[Recommendation]:
    """Recomendações por prioridade (alta primeiro), estável — preserva a ordem do recommender."""
    return sorted(recs, key=lambda r: _PRIORITY_RANK.get(r.prioridade, 1))


def _resumo_executivo(
    empresa: str, aimi: AIMIScore, recs: Sequence[Recommendation]
) -> str:
    """Resumo executivo PT-BR: classe + AIMI + principal gap + as techs prescritas (aterrado)."""
    gap = gap_pillars(aimi)[0]  # o pilar mais severo (mesma seleção do RAG/F3.7 e das regras/F4.1)
    gap_label = _PILLAR_PT[gap.pilar]
    base = (
        f"{empresa} foi diagnosticada como {aimi.classificacao.value} com AIMI "
        f"{aimi.total}/100. O principal gap está em {gap_label} — {gap.score}/25 "
        f"({gap.band.value if gap.band else 'n/d'})."
    )
    if not recs:
        return (
            f"{base} Não há, no momento, tecnologia NVIDIA recomendável com evidência suficiente "
            "dos dois lados; o run registra o diagnóstico e segue para coleta adicional."
        )
    techs = ", ".join(r.tech for r in _by_priority(recs))
    return (
        f"{base} Recomendamos {len(recs)} tecnologia(s) NVIDIA — {techs} — para fechar o gap, "
        "cada uma sustentada por evidência dos dois lados (perfil da startup + base NVIDIA)."
    )


def _acao_comercial(aimi: AIMIScore, recs: Sequence[Recommendation]) -> str:
    """Eixo comercial: abordagem/timing de outreach pela região do plano `classe × AIMI` (§6)."""
    classe = aimi.classificacao.value
    gap = gap_pillars(aimi)[0]
    is_graduation = gap.pilar is AIMIPillar.TECHNICAL_OPTIMIZATION and bool(recs)
    if is_graduation:
        return (
            f"Priorizar o outreach: {classe} com gap de inferência (Technical Optimization) é o "
            "alvo de graduação API→stack — o perfil de maior upside para o Inception. Abordagem "
            "técnica, ancorada no ROI de internalizar a inferência (GPU Graduation Engine)."
        )
    if aimi.total >= 60:
        return (
            f"Outreach de relacionamento: {classe} com AIMI {aimi.total}/100 (maturidade alta) — "
            "foco em parceria/distribuição (P4) e co-marketing, não em internalizar inferência."
        )
    return (
        f"Outreach de nutrição: {classe} com AIMI {aimi.total}/100 — qualificar o caso de uso e "
        f"o gap em {_PILLAR_PT[gap.pilar]} antes de uma abordagem comercial mais forte."
    )


def _acao_tecnica(recs: Sequence[Recommendation]) -> str:
    """Eixo técnico: ancorado na recomendação de maior prioridade (proxima_acao já vem do F4.3)."""
    if not recs:
        return (
            "Sem tecnologia NVIDIA recomendável com evidência suficiente neste momento; revisar à "
            "medida que mais evidência do perfil for coletada."
        )
    ordered = _by_priority(recs)
    top = ordered[0]
    roadmap = " → ".join(r.tech for r in ordered)
    return (
        f"Começar por {top.tech} ({top.prioridade.value} prioridade, complexidade "
        f"{top.complexidade.value}): {top.proxima_acao} Roadmap sugerido: {roadmap}."
    )


def _acao_comunitaria(recs: Sequence[Recommendation]) -> str:
    """Eixo comunitário: onboarding Inception atado às techs prescritas (créditos as destravam)."""
    if not recs:
        return (
            "Convidar para o NVIDIA Inception: onboarding com créditos de GPU/cloud, acesso a NIM/"
            "NeMo via build.nvidia.com, suporte técnico, eventos e comunidade (GTM)."
        )
    return (
        "Onboarding no NVIDIA Inception para destravar a execução: créditos de GPU/cloud e acesso "
        "a NIM/NeMo via build.nvidia.com cobrem o custo inicial das recomendações técnicas; somar "
        "suporte, eventos e a comunidade (GTM) do programa."
    )


def build_briefing(
    aimi: AIMIScore,
    profile: StartupProfile | None,
    recommendations: Sequence[Recommendation],
    *,
    empresa: str,
    run_id: str | None = None,
) -> Briefing:
    """Espinha determinista do briefing **normal** (§2): diagnóstico + recomendações → `Briefing`.

    Monta o relatório a partir do que já está no estado — o `aimi` (F2.6) e as recomendações
    (F4.2/F4.3), **ambos já aterrados em evidência** — preenchendo o resumo executivo e os três
    eixos de ação (§2) com esqueletos PT-BR coerentes (que o Super refina, se ligado).
    Determinístico e offline: nenhuma afirmação nova além do que o diagnóstico/recomendações
    sustentam (o Guardrails da F4.5 reforça). `generated_at` fica `None` p/ run reprodutível (sem
    `now()`, igual aos terminais e à data da evidência NVIDIA/F4.3).
    """
    recs = list(recommendations)
    return Briefing(
        empresa=empresa,
        status=BriefingStatus.NORMAL,
        resumo_executivo=_resumo_executivo(empresa, aimi, recs),
        aimi=aimi,
        recomendacoes=recs,
        acao_comercial=_acao_comercial(aimi, recs),
        acao_tecnica=_acao_tecnica(recs),
        acao_comunitaria=_acao_comunitaria(recs),
        # F6.13 — a prioridade de outreach (fila do gerente) no artefato de decisão.
        inception_priority=inception_priority(aimi)[0],
        run_id=run_id,
    )


# ----------------------------------------------------------------------- Markdown (view PT-BR)


def _evidence_urls(items: Sequence[Any]) -> str:
    """URLs distintas (ordem preservada) de uma lista de `Evidence`, p/ a linha de proveniência."""
    seen: list[str] = []
    for ev in items:
        url = str(ev.url)
        if url not in seen:
            seen.append(url)
    return ", ".join(seen) if seen else "—"


def _aimi_lines(aimi: AIMIScore) -> list[str]:
    """Linhas do bloco AIMI no Markdown (classe + os 4 pilares com score/faixa/justificativa)."""
    prio, fatores = inception_priority(aimi)  # F6.13 — score explicável (fatores na mesma linha)
    lines = [
        f"- **Classe:** {aimi.classificacao.value}",
        f"- **AIMI total:** {aimi.total}/100",
        f"- **Inception Priority:** {prio}/100 — {fatores}.",
    ]
    for p in aimi.pillars:
        banda = p.band.value if p.band else "n/d"
        lines.append(f"- **{_PILLAR_PT[p.pilar]}:** {p.score}/25 ({banda}) — {p.justificativa}")
    return lines


def _delta_pct(pct: float) -> str:
    """Delta percentual com sinal explícito; negativo = melhora (menos custo/latência). Espelha o
    `deltaPct` da UI (`detail.tsx`) p/ o texto do briefing bater com o cartão `RoiStrip`."""
    return f"{'+' if pct > 0 else ''}{pct}%"


def _roi_summary(roi: ROIEstimate) -> str | None:
    """Resumo PT-BR de uma linha do ROI (F6) p/ o texto do briefing — paridade com o `RoiStrip`.

    Mostra **só os números que existem** (throughput / custo / p95), a migração `baseline →
    otimizado` e a **proveniência honesta**: `medido ao vivo` vs `matriz de benchmark` (+ a fonte da
    célula, que já carrega o rótulo "ilustrativo" enquanto não for medição). `None` quando não há
    métrica nem migração — a recomendação degrada graciosa, sem inventar ROI (F5.6).
    """
    partes: list[str] = []
    if roi.throughput_speedup is not None:
        partes.append(f"throughput {roi.throughput_speedup}x")
    if roi.cost_delta_pct is not None:
        partes.append(f"custo {_delta_pct(roi.cost_delta_pct)}")
    if roi.latency_p95_delta_pct is not None:
        partes.append(f"p95 {_delta_pct(roi.latency_p95_delta_pct)}")
    migracao = f"{roi.baseline} → {roi.optimized}" if roi.baseline and roi.optimized else None
    if not partes and migracao is None:
        return None
    texto = ", ".join(partes) if partes else "sem números"
    if migracao:
        texto += f" ({migracao})"
    texto += "; medido ao vivo" if roi.is_live_run else "; matriz de benchmark"
    if roi.benchmark_source:
        texto += f" · fonte: {roi.benchmark_source}"
    return texto


def _rec_lines(rec: Recommendation) -> list[str]:
    """Bloco Markdown de uma recomendação (§5.5): evidências dos dois lados (+ ROI, se houver)."""
    lines = [
        f"### {rec.tech} — prioridade {rec.prioridade.value} · "
        f"complexidade {rec.complexidade.value}",
        f"- **Justificativa técnica:** {rec.justificativa_tecnica}",
        f"- **Justificativa de negócio:** {rec.justificativa_negocio}",
        f"- **Próxima ação:** {rec.proxima_acao}",
        f"- **Evidência (gap da startup):** {_evidence_urls(rec.evidencia_gap)}",
        f"- **Evidência (NVIDIA):** {_evidence_urls(rec.evidencia_nvidia)}",
    ]
    roi = _roi_summary(rec.roi) if rec.roi is not None else None
    if roi is not None:
        lines.append(f"- **ROI (graduação de inferência):** {roi}")
    return lines


def render_markdown(briefing: Briefing) -> str:
    """Renderiza o `Briefing` como Markdown PT-BR (a view do JSON, F4.4 — base do PDF/F4.6 e front).

    Cobre **todas** as variantes (normal + terminais F2.12/F2.13): resumo, diagnóstico AIMI (se há),
    recomendações (se há), os três eixos de ação (§2) e as lacunas (terminal de dados insuf.).
    Determinístico — derivado só do objeto, sem `now()`/rede; o que não há no briefing é omitido.
    """
    out: list[str] = [f"# Briefing executivo — {briefing.empresa}", ""]
    out.append(f"**Status:** {briefing.status.value} · **Idioma:** {briefing.idioma}")
    out += ["", "## Resumo executivo", briefing.resumo_executivo]

    if briefing.aimi is not None:
        out += ["", "## Diagnóstico (AIMI)", *_aimi_lines(briefing.aimi)]

    if briefing.recomendacoes:
        out += ["", "## Recomendações NVIDIA"]
        for rec in briefing.recomendacoes:
            out += ["", *_rec_lines(rec)]

    acoes = [
        ("Comercial", briefing.acao_comercial),
        ("Técnica", briefing.acao_tecnica),
        ("Comunidade (Inception)", briefing.acao_comunitaria),
    ]
    if any(texto for _, texto in acoes):
        out += ["", "## Próximas ações"]
        out += [f"- **{eixo}:** {texto}" for eixo, texto in acoes if texto]

    if briefing.lacunas:
        out += ["", "## Lacunas"]
        out += [f"- {lac}" for lac in briefing.lacunas]

    return "\n".join(out)


# ------------------------------------------------------------------- PDF (view server-side, F4.6)


def _pdf_escape(text: str) -> str:
    """Escapa &/</> p/ o texto dinâmico não colidir com os mini-markups (`<b>`) do Paragraph."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pdf_field(label: str, value: str) -> str:
    """Linha `**rótulo:** valor` do Markdown traduzida p/ o `<b>` inline do Paragraph (escapada)."""
    return f"<b>{_pdf_escape(label)}:</b> {_pdf_escape(value)}"


def render_pdf(briefing: Briefing) -> bytes:
    """Renderiza o `Briefing` como PDF A4 (a view server-side do JSON, F4.6 — irmã do `render_markdown`).

    **Mesma estrutura/conteúdo do Markdown** (resumo, diagnóstico AIMI, recomendações com evidência
    dos dois lados, os três eixos §2 e as lacunas), derivada **só do objeto** — sem `now()`/rede,
    reusando os mesmos helpers de dados (`_evidence_urls`, `_PILLAR_PT`). Saída **determinística**
    (`invariant=1`: o reportlab fixa data e ID do PDF) p/ run reprodutível, igual ao resto do briefing
    (`generated_at=None`). O reportlab é importado **preguiçosamente** (a espinha do módulo —
    `build_briefing`/`render_markdown`/o nó — importa offline mesmo sem a dep, igual à disciplina de
    imports do projeto). Devolve os **bytes** do PDF: a API (`GET /briefings/{id}`, F5.2) e o front
    (F5) servem daqui; cobre todas as variantes (normal + terminais F2.12/F2.13).
    """  # noqa: E501 — a linha de sumário do docstring excede 100 de propósito (1 frase)
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    title, h2, h3, body = (
        styles["Title"],
        styles["Heading2"],
        styles["Heading3"],
        styles["BodyText"],
    )
    gap = Spacer(1, 8)

    story: list = [
        Paragraph(_pdf_escape(f"Briefing executivo — {briefing.empresa}"), title),
        Paragraph(_pdf_field("Status", briefing.status.value), body),
        Paragraph(_pdf_field("Idioma", briefing.idioma), body),
        gap,
        Paragraph("Resumo executivo", h2),
        Paragraph(_pdf_escape(briefing.resumo_executivo), body),
    ]

    if briefing.aimi is not None:
        story += [gap, Paragraph("Diagnóstico (AIMI)", h2)]
        story.append(Paragraph(_pdf_field("Classe", briefing.aimi.classificacao.value), body))
        story.append(Paragraph(_pdf_field("AIMI total", f"{briefing.aimi.total}/100"), body))
        prio, fatores = inception_priority(briefing.aimi)  # F6.13 — paridade com o Markdown
        story.append(Paragraph(_pdf_field("Inception Priority", f"{prio}/100 — {fatores}."), body))
        for p in briefing.aimi.pillars:
            banda = p.band.value if p.band else "n/d"
            story.append(
                Paragraph(
                    _pdf_field(_PILLAR_PT[p.pilar], f"{p.score}/25 ({banda}) — {p.justificativa}"),
                    body,
                )
            )

    if briefing.recomendacoes:
        story += [gap, Paragraph("Recomendações NVIDIA", h2)]
        for rec in briefing.recomendacoes:  # ordem do estado (igual ao render_markdown)
            head = (
                f"{rec.tech} — prioridade {rec.prioridade.value} · "
                f"complexidade {rec.complexidade.value}"
            )
            story.append(Paragraph(_pdf_escape(head), h3))
            campos = [
                ("Justificativa técnica", rec.justificativa_tecnica),
                ("Justificativa de negócio", rec.justificativa_negocio),
                ("Próxima ação", rec.proxima_acao),
                ("Evidência (gap da startup)", _evidence_urls(rec.evidencia_gap)),
                ("Evidência (NVIDIA)", _evidence_urls(rec.evidencia_nvidia)),
            ]
            roi = _roi_summary(rec.roi) if rec.roi is not None else None
            if roi is not None:
                campos.append(("ROI (graduação de inferência)", roi))
            for label, value in campos:
                story.append(Paragraph(_pdf_field(label, value), body))

    acoes = [
        ("Comercial", briefing.acao_comercial),
        ("Técnica", briefing.acao_tecnica),
        ("Comunidade (Inception)", briefing.acao_comunitaria),
    ]
    if any(texto for _, texto in acoes):
        story += [gap, Paragraph("Próximas ações", h2)]
        story += [Paragraph(_pdf_field(eixo, texto), body) for eixo, texto in acoes if texto]

    if briefing.lacunas:
        story += [gap, Paragraph("Lacunas", h2)]
        story += [Paragraph(_pdf_escape(lac), body) for lac in briefing.lacunas]

    buf = BytesIO()
    # invariant=1 → data e ID do PDF fixos: mesmos bytes a cada chamada (run reprodutível, F4.4).
    SimpleDocTemplate(
        buf, pagesize=A4, invariant=1, title=f"Briefing executivo — {briefing.empresa}"
    ).build(story)
    return buf.getvalue()


# ------------------------------------------------------------------ caminho LLM (opt-in, refino)


def _json_slice(text: str) -> str:
    """Recorta do primeiro `{` ao último `}` — tolera cercas ```json``` e texto ao redor."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("sem objeto JSON na resposta do briefing")
    return text[start : end + 1]


#: Campos **textuais** que o LLM pode refinar — só eles (diagnóstico/recomendações ficam intactos).
_REFINABLE: tuple[str, ...] = (
    "resumo_executivo",
    "acao_comercial",
    "acao_tecnica",
    "acao_comunitaria",
)


def parse_refinement(text: str) -> dict[str, str]:
    """JSON do Super → refino dos campos textuais (`{campo: texto}`). Tolerante (padrão dos F2)."""
    data = json.loads(_json_slice(text))
    if not isinstance(data, dict):
        raise ValueError("JSON do briefing não é um objeto")
    out: dict[str, str] = {}
    for field in _REFINABLE:
        val = data.get(field)
        if isinstance(val, str) and val.strip():
            out[field] = val.strip()
    return out


def _apply_refinement(skeleton: Briefing, ref: dict[str, str]) -> Briefing:
    """Sobrescreve só os campos textuais não-vazios; diagnóstico/recomendações/status intactos.

    A evidência (aimi + recomendações) **nunca vem do LLM** — é sempre a do estado (anti-alucinação,
    igual ao recommender/F4.2). O modelo refina a prosa, não a proveniência.
    """
    update = {f: ref[f] for f in _REFINABLE if f in ref}
    return skeleton.model_copy(update=update) if update else skeleton


def refine_with_llm(skeleton: Briefing, *, refine: RefineFn) -> Briefing | None:
    """Roda o adapter e aplica o refino ao esqueleto; **degrada p/ `None`** a qualquer falha.

    Núcleo testável do caminho LLM: o adapter (fake nos testes, Super em produção) devolve o JSON
    cru; aqui só parse + merge **preservando diagnóstico e recomendações**. Erro de rede/JSON vira
    `None` → o caller fica com a espinha determinista (não alucina).
    """
    try:
        ref = parse_refinement(refine(skeleton))
    except Exception:  # noqa: BLE001 — LLM/parse falhou → fallback à espinha determinista
        return None
    return _apply_refinement(skeleton, ref)


def _default_refine(skeleton: Briefing, *, run_id: str | None = None) -> str:
    """Adapter real: Nemotron-Super (reasoning ON, F0.7) + prompt versionado (F0.12). Rede.

    Imports preguiçosos (o módulo importa offline sem langchain/Langfuse). Manda o esqueleto do
    briefing (diagnóstico + recomendações já com evidência) p/ o modelo refinar **só a redação**
    ancorado nele — não inventa fato fora do que o estado sustenta. `traced_config` carimba o tag no
    trace (F0.8); o cache (F2.14) casa a chamada entre runs.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    from packages.observability import traced_config

    from .cache import cached_completion
    from .llm import reasoning_system_message
    from .prompts import get_prompt

    prompt = get_prompt("briefing")
    config = traced_config(node="briefing", prompt_version=prompt.version_tag, run_id=run_id)
    payload = skeleton.model_dump_json()
    messages: list = []
    if prompt.reasoning:
        messages.append(reasoning_system_message(True))
    messages.append(SystemMessage(content=prompt.template))
    messages.append(HumanMessage(content=payload))
    return cached_completion(prompt, messages, config=config)  # cache F2.14


def make_briefing(
    aimi: AIMIScore,
    profile: StartupProfile | None,
    recommendations: Sequence[Recommendation],
    *,
    empresa: str,
    run_id: str | None = None,
    refine: RefineFn | None = None,
) -> Briefing:
    """Briefing final: espinha determinista por padrão; o Super refina a redação se ligado.

    Igual ao recommender (F4.2): default offline/reproduzível; o LLM entra por
    `settings.briefing_use_llm` (+ chave) ou por um adapter `refine=` injetado, e qualquer falha cai
    de volta na espinha. Diagnóstico e recomendações são sempre os do estado (anti-alucinação).
    """
    base = build_briefing(aimi, profile, recommendations, empresa=empresa, run_id=run_id)
    if refine is None and not get_settings().briefing_use_llm:
        return base  # default determinista/offline (reproduzível)
    adapter: RefineFn = refine or (lambda b: _default_refine(b, run_id=run_id))
    refined = refine_with_llm(base, refine=adapter)
    return refined if refined is not None else base


# ------------------------------------------------------------------------------- nó


def briefing(
    state: GraphState, *, refine: RefineFn | None = None, guard: GuardFn | None = None
) -> dict:
    """F4.4/F4.5 — relatório executivo PT-BR (§2), despachando por status; update parcial.

    Variantes terminais (status já cravado pelo evidence_validator/F2.7 ao saltar RAG/recomendação):
    - `INSUFFICIENT_DATA` (F2.12) → briefing **"dados insuficientes"** (o apurado + lacunas);
    - `OUT_OF_SCOPE` (F2.13) → briefing **"fora de escopo"** (non-AI de alta confiança).
    Nenhum força recomendação NVIDIA. Caminho **normal**: sem `aimi` (espinha offline sem
    classificação) é um no-op limpo (só fecha o run em COMPLETED) — grafo verde ponta a ponta
    (M2/DoD) sem alucinar relatório sem base; com diagnóstico, passa as recomendações pelo **rail de
    evidência** (F4.5: descarta as sem os dois lados **antes** de virar texto), monta o briefing
    normal (§2) sobre as aprovadas e fecha, carimbando `trace["guardrails"]`. `refine`/`guard` são
    injetáveis (testes/worker); por default a espinha determinista (Super/NeMo plugáveis).
    """
    if state.status is RunStatus.INSUFFICIENT_DATA:
        return {"briefing": insufficient_data_briefing(state)}  # status já é terminal
    if state.status is RunStatus.OUT_OF_SCOPE:
        return {"briefing": out_of_scope_briefing(state)}  # status já é terminal

    aimi = state.aimi
    if aimi is None:
        return {"status": RunStatus.COMPLETED}  # sem diagnóstico → sem briefing (espinha verde M2)

    # F4.5 — output rail: só recomendação com evidência dos dois lados sustenta o briefing.
    rail = guard_recommendations(state.recommendations, guard=guard)
    profile = state.profile
    empresa = (profile.nome if profile is not None else None) or state.query
    report = make_briefing(
        aimi, profile, rail.aprovadas, empresa=empresa, run_id=state.run_id, refine=refine
    )
    trace = {**state.trace, "guardrails": rail.trace()}
    return {"briefing": report, "status": RunStatus.COMPLETED, "trace": trace}


__all__ = [
    "RefineFn",
    "GuardFn",
    "build_briefing",
    "render_markdown",
    "render_pdf",
    "parse_refinement",
    "refine_with_llm",
    "make_briefing",
    "briefing",
]
