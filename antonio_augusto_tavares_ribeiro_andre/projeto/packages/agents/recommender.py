"""Nó **recommender** (F4.2/F4.3): gaps do AIMI × evidência NVIDIA → `Recommendation` dos 2 lados.

Sétimo nó do grafo (ARQUITETURA §3), entre o `nvidia_rag` (F3.7) e o `gpu_benchmark` (F6). É o
**núcleo do apoio à decisão** (DSS nível 1, `docs/ARQUITETURA.md §3.5/§3.6`): converte o
diagnóstico (perfil + AIMI) na **prescrição** acionável — *o que ofereço a esta startup?* Cruza as
duas pontas já preparadas pelas tasks anteriores:

- **lado startup (`evidencia_gap`)** — o gap que motiva: o pilar-gap do AIMI (F2.6) com sua
  evidência, ou, numa tech de setor, o domínio declarado no perfil (§5.5);
- **lado NVIDIA (`evidencia_nvidia`)** — a citação da KB recuperada pelo `nvidia_rag` (F3.7),
  casada à candidata por **`kb_tech`** (a mesma chave do mapa de regras F4.1).

A `Recommendation` (F4.3, schema F0.5) **exige os dois lados**; o nó **só emite** o que tem ambos —
o invariante que o NeMo Guardrails (F4.5) reforça no briefing. Candidata sem citação NVIDIA (ou sem
evidência de gap) é descartada: sem evidência completa não há recomendação (não se alucina).

**Decisão de design (espinha verde, igual classifier/F2.6 e todo o F3/F4.1):** o caminho
**determinista/offline é o default** — a `Recommendation` é montada a partir do esqueleto §5.5 das
regras (F4.1) com a evidência resolvida, sem rede/LLM/GPU (runs reprodutíveis). A peça LLM
(Nemotron-Super, reasoning ON — `recommender@v1`, F0.12) é **plugável** atrás de
`settings.recommender_use_llm` (+ chave) **ou** de um adapter `recommend=` injetado, e **refina só a
redação** (justificativas/próxima-ação/prioridade), caindo de volta na espinha a qualquer falha. A
**evidência dos dois lados nunca vem do LLM** — é sempre a determinista (anti-alucinação, como no
classifier). Sem `aimi` (espinha offline sem classificação) o nó é um **no-op limpo** (`{}`).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from packages.config import get_settings
from packages.rag import load_kb_sources
from packages.schemas import (
    AIMIPillar,
    AIMIScore,
    Complexity,
    Evidence,
    GraphState,
    Priority,
    Recommendation,
    RetrievedChunk,
    StartupProfile,
)
from packages.scraping.provenance import make_snippet

from .recommend_rules import TechCandidate, match_techs

# Adapter de refino injetável: esqueletos de recomendação -> JSON cru do modelo. Default = Super.
RecommendFn = Callable[[Sequence[Recommendation]], str]

#: Teto de citações NVIDIA por recomendação (briefing enxuto; o `nvidia_rag` já limita o total em
#: `MAX_CITATIONS`). As mais relevantes primeiro — `state.retrieved` já vem ordenado por rerank.
MAX_NVIDIA_EVIDENCE = 3


# ------------------------------------------------------------- evidência NVIDIA (lado direito)


@lru_cache(maxsize=1)
def _kb_captured_at() -> dict[str, datetime]:
    """doc_id (F3.1) → instante do snapshot curado da KB, p/ **datar** a evidência NVIDIA.

    A `Evidence` exige `fetched_at`; a citação recuperada (F3.7) não carrega a data, então ela vem
    do manifesto (`captured_at`, F3.1) pelo doc da fonte — estável/determinístico (sem `now()`).
    """
    return {
        s.id: datetime(s.captured_at.year, s.captured_at.month, s.captured_at.day, tzinfo=UTC)
        for s in load_kb_sources()
    }


def _doc_id(chunk_id: str) -> str:
    """doc da fonte a partir do chunk_id estável `<doc_id>::<idx>` (F3.2)."""
    return chunk_id.rsplit("::", 1)[0]


def _dedup_ev(evidence: Iterable[Evidence]) -> list[Evidence]:
    """Dedup de evidências por (url, snippet), preservando a ordem (igual ao classifier)."""
    seen: set[tuple[str, str]] = set()
    out: list[Evidence] = []
    for ev in evidence:
        key = (str(ev.url), ev.snippet)
        if key not in seen:
            seen.add(key)
            out.append(ev)
    return out


def _nvidia_evidence(chunk: RetrievedChunk) -> Evidence | None:
    """Converte uma citação recuperada (F3.7) num átomo `Evidence` citável; `None` se não-citável.

    Sem `source_url` (proveniência) ou fora do manifesto (sem data de snapshot) não há evidência:
    não se cita o que não se pode linkar/datar (princípio de evidência §8).
    """
    url = chunk.source_url
    if url is None:
        return None
    captured = _kb_captured_at().get(_doc_id(str(chunk.metadata.get("chunk_id", ""))))
    if captured is None:
        return None
    try:
        return Evidence(
            url=str(url),
            snippet=make_snippet(chunk.text),
            fetched_at=captured,
            source_title=chunk.source_title,
        )
    except Exception:  # noqa: BLE001 — url/campo inválido p/ Evidence → não cita
        return None


def nvidia_evidence_for(kb_tech: str, retrieved: Sequence[RetrievedChunk]) -> list[Evidence]:
    """Citações da KB cujo `tech` casa o `kb_tech` da candidata (lado NVIDIA), as mais relevantes.

    `retrieved` (F3.7) já vem ordenado por relevância (rerank desc); filtra por tech, converte em
    `Evidence` datada/citável, deduplica e corta em `MAX_NVIDIA_EVIDENCE`.
    """
    out: list[Evidence] = []
    for chunk in retrieved:
        if chunk.metadata.get("tech") != kb_tech:
            continue
        ev = _nvidia_evidence(chunk)
        if ev is not None:
            out.append(ev)
    return _dedup_ev(out)[:MAX_NVIDIA_EVIDENCE]


# ------------------------------------------------------------- evidência de gap (lado esquerdo)


def _pillar_evidence(aimi: AIMIScore, pilar: AIMIPillar) -> list[Evidence]:
    """Evidência do pilar-gap que disparou a candidata (rastreabilidade gap→tech, F4.1)."""
    for ps in aimi.pillars:
        if ps.pilar is pilar:
            return list(ps.evidencia)
    return []


def _profile_evidence(profile: StartupProfile | None) -> list[Evidence]:
    """Evidência pública que ancora o diagnóstico: o que a startup **diz ser** (descrição + techs).

    Fallback do gap quando o pilar não tem evidência própria: um gap de **ausência** (ex.: P3 de um
    wrapper 100% API — score ≤6, que a RUBRICA não obriga a citar) não tem evidência positiva no
    pilar, mas é fundamentado pelo perfil público (a descrição/stack que revelam a dependência).
    """
    if profile is None:
        return []
    ev: list[Evidence] = []
    if profile.descricao is not None:
        ev.extend(profile.descricao.evidence)
    for tech in profile.tecnologias:
        ev.extend(tech.evidence)
    return _dedup_ev(ev)


def _sector_evidence(profile: StartupProfile | None) -> list[Evidence]:
    """Evidência do lado startup p/ uma tech de setor: o domínio declarado (setor + descrição)."""
    if profile is None:
        return []
    ev: list[Evidence] = []
    if profile.setor is not None:
        ev.extend(profile.setor.evidence)
    if profile.descricao is not None:
        ev.extend(profile.descricao.evidence)
    return _dedup_ev(ev)


def gap_evidence_for(
    cand: TechCandidate, aimi: AIMIScore, profile: StartupProfile | None
) -> list[Evidence]:
    """Evidência do lado startup que motiva a candidata: o pilar-gap (ou o setor, §5.5).

    Pilar-gap com evidência própria → usa-a (rastreabilidade gap→tech). Gap de **ausência** sem
    evidência no pilar (P3 de um wrapper, score ≤6) → ancora no perfil público (`_profile_evidence`)
    p/ que a recomendação mais valiosa (graduação API→stack) não caia por falta do lado-startup.
    """
    if cand.pilar_origem is not None:
        return _pillar_evidence(aimi, cand.pilar_origem) or _profile_evidence(profile)
    return _sector_evidence(profile)


# ---------------------------------------------------------------- espinha determinista (F4.2/F4.3)


def build_recommendations(
    aimi: AIMIScore,
    profile: StartupProfile | None,
    retrieved: Sequence[RetrievedChunk],
) -> list[Recommendation]:
    """Espinha determinista: cruza as candidatas (F4.1) × citações (F3.7) por `kb_tech` → §5.5.

    Para cada candidata monta a `Recommendation` a partir do esqueleto §5.5 da regra (F4.1) com a
    **evidência dos dois lados** resolvida (`evidencia_gap` do pilar/setor + `evidencia_nvidia` das
    citações casadas por tech). **Só emite** quando os dois lados existem (invariante F4.5: sem
    evidência completa não há recomendação). Determinístico (herda a ordem de `match_techs`).
    """
    recs: list[Recommendation] = []
    for cand in match_techs(aimi, profile):
        nvidia = nvidia_evidence_for(cand.rule.kb_tech, retrieved)
        gap = gap_evidence_for(cand, aimi, profile)
        if not nvidia or not gap:
            continue  # falta um dos lados → não recomenda (Guardrails F4.5)
        rule = cand.rule
        recs.append(
            Recommendation(
                tech=rule.tech,
                justificativa_tecnica=rule.justificativa_tecnica,
                justificativa_negocio=rule.justificativa_negocio,
                prioridade=rule.prioridade,
                complexidade=rule.complexidade,
                proxima_acao=rule.proxima_acao,
                pilar_origem=cand.pilar_origem,
                evidencia_gap=gap,
                evidencia_nvidia=nvidia,
            )
        )
    return recs


# ------------------------------------------------------------------ caminho LLM (opt-in)


def _json_slice(text: str) -> str:
    """Recorta a lista JSON (do primeiro `[` ao último `]`) — tolera cercas e texto ao redor."""
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("sem lista JSON na resposta do recommender")
    return text[start : end + 1]


_PRIORITY = {p.value: p for p in Priority}
_COMPLEXITY = {c.value: c for c in Complexity}


def _parse_enum(value: Any, mapping: dict[str, Any]) -> Any | None:
    """Normaliza prioridade/complexidade vinda do modelo (case-insensitive); `None` se não casar."""
    if value is None:
        return None
    return mapping.get(str(value).strip().lower())


def parse_refinements(text: str) -> dict[str, dict]:
    """JSON do Super → refino por tech (`{tech: {...}}`). Tolerante (no padrão dos parsers F2)."""
    data = json.loads(_json_slice(text))
    out: dict[str, dict] = {}
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict) and str(item.get("tech", "")).strip():
            out[str(item["tech"]).strip()] = item
    return out


def _apply_refinement(rec: Recommendation, ref: dict | None) -> Recommendation:
    """Sobrescreve só os campos **textuais** (e prioridade/complexidade) com o refino não-vazio.

    A **evidência dos dois lados fica intacta** — vem da espinha determinista (F4.1/F3.7); o LLM
    refina a redação, nunca a proveniência (anti-alucinação, igual ao classifier/F2.6).
    """
    if not ref:
        return rec
    update: dict[str, Any] = {}
    for f in ("justificativa_tecnica", "justificativa_negocio", "proxima_acao"):
        val = str(ref.get(f, "")).strip()
        if val:
            update[f] = val
    pr = _parse_enum(ref.get("prioridade"), _PRIORITY)
    if pr is not None:
        update["prioridade"] = pr
    cx = _parse_enum(ref.get("complexidade"), _COMPLEXITY)
    if cx is not None:
        update["complexidade"] = cx
    return rec.model_copy(update=update) if update else rec


def recommend_with_llm(
    skeletons: Sequence[Recommendation], *, recommend: RecommendFn
) -> list[Recommendation] | None:
    """Roda o adapter e aplica o refino sobre os esqueletos; **degrada p/ `None`** a qualquer falha.

    Núcleo testável do caminho LLM: o adapter (fake nos testes, Super em produção) devolve o JSON
    cru de refino; aqui só parse + merge **preservando a evidência**. Erro de rede/JSON vira `None`
    → o caller fica com a espinha determinista (não alucina).
    """
    try:
        refinements = parse_refinements(recommend(skeletons))
    except Exception:  # noqa: BLE001 — LLM/parse falhou → fallback à espinha determinista
        return None
    return [_apply_refinement(s, refinements.get(s.tech)) for s in skeletons]


def _default_recommend(
    skeletons: Sequence[Recommendation],
    *,
    profile: StartupProfile | None,
    aimi: AIMIScore,
    run_id: str | None = None,
) -> str:
    """Adapter real: Nemotron-Super (reasoning ON, F0.7) + prompt versionado (F0.12). Rede.

    Imports preguiçosos (o módulo importa offline sem langchain/Langfuse). Manda o diagnóstico + as
    candidatas **com a evidência NVIDIA já recuperada** (F3.7), p/ o modelo ancorar a redação nas
    citações — não inventa capacidade fora delas. `traced_config` carimba o version_tag no trace
    (F0.8); o cache (F2.14) casa a chamada entre runs.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    from packages.observability import traced_config

    from .cache import cached_completion
    from .llm import reasoning_system_message
    from .prompts import get_prompt

    prompt = get_prompt("recommender")
    config = traced_config(node="recommender", prompt_version=prompt.version_tag, run_id=run_id)
    payload = json.dumps(
        {
            "perfil": profile.model_dump(mode="json") if profile is not None else None,
            "aimi": aimi.model_dump(mode="json"),
            "candidatas": [
                {
                    "tech": r.tech,
                    "pilar_origem": r.pilar_origem.value if r.pilar_origem else None,
                    "evidencia_nvidia": [
                        {"url": str(e.url), "trecho": e.snippet} for e in r.evidencia_nvidia
                    ],
                }
                for r in skeletons
            ],
        },
        ensure_ascii=False,
    )
    messages: list = []
    if prompt.reasoning:
        messages.append(reasoning_system_message(True))
    messages.append(SystemMessage(content=prompt.template))
    messages.append(HumanMessage(content=payload))
    return cached_completion(prompt, messages, config=config)  # cache F2.14


def make_recommendations(
    aimi: AIMIScore,
    profile: StartupProfile | None,
    retrieved: Sequence[RetrievedChunk],
    *,
    recommend: RecommendFn | None = None,
    run_id: str | None = None,
) -> list[Recommendation]:
    """Recomendações finais: espinha determinista por padrão; Super refina se ligado, com fallback.

    Igual ao classifier (F2.6): default offline/reproduzível; o LLM entra por
    `settings.recommender_use_llm` (+ chave) ou por um adapter `recommend=` injetado, e qualquer
    falha cai de volta na espinha. A evidência dos dois lados é sempre a determinista.
    """
    base = build_recommendations(aimi, profile, retrieved)
    if not base:
        return base
    if recommend is None and not get_settings().recommender_use_llm:
        return base  # default determinista/offline (reproduzível)
    adapter: RecommendFn = recommend or (
        lambda s: _default_recommend(s, profile=profile, aimi=aimi, run_id=run_id)
    )
    refined = recommend_with_llm(base, recommend=adapter)
    return refined if refined is not None else base


# ------------------------------------------------------------------------------- nó


def recommender(state: GraphState, *, recommend: RecommendFn | None = None) -> dict:
    """F4.2/F4.3 — cruza gaps do AIMI × evidência NVIDIA → recomendações 2 lados; update parcial.

    Sem `aimi` (espinha offline sem classificação) é um no-op limpo (`{}`) — `recommendations` fica
    `[]`, grafo verde ponta a ponta (M2/DoD) sem recomendar sobre diagnóstico inexistente. Com
    diagnóstico, monta a `Recommendation` (§5.5) cruzando as candidatas (F4.1) com a evidência
    recuperada (F3.7) e emite **só o que tem evidência dos dois lados** (Guardrails F4.5).
    `recommend` é injetável (testes/worker); por default usa a espinha determinista, com o Super
    plugável (`settings.recommender_use_llm`).
    """
    aimi = state.aimi
    if aimi is None:
        return {}  # nada a recomendar (offline default) → recommendations [], espinha verde (M2)
    recs = make_recommendations(
        aimi, state.profile, state.retrieved, recommend=recommend, run_id=state.run_id
    )
    if not recs:
        return {}  # nenhuma candidata com evidência dos 2 lados → sem recomendação (não alucina)
    trace = {**state.trace, "recommender": {"n": len(recs), "techs": [r.tech for r in recs]}}
    return {"recommendations": recs, "trace": trace}


__all__ = [
    "MAX_NVIDIA_EVIDENCE",
    "RecommendFn",
    "nvidia_evidence_for",
    "gap_evidence_for",
    "build_recommendations",
    "parse_refinements",
    "recommend_with_llm",
    "make_recommendations",
    "recommender",
]
