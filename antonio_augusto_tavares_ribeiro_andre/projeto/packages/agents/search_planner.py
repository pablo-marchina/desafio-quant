"""Nó **search_planner** (F2.3): consulta → termos de busca + fontes priorizadas.

Primeiro nó do grafo (ARQUITETURA §3). Transforma a consulta do usuário num **plano
de coleta** que o scraper (F2.4) consome: `search_terms` (termos largos p/ a busca
F1.1) + `sources` (onde olhar, §9). Dois modos (contrato F2.3):

- **single_company** — lookup de uma empresa (nome/domínio): termos com variantes
  do nome + fontes de alvo (site oficial, LinkedIn, base, notícia).
- **discovery** — descoberta por setor/região (ex.: "fintechs AI em SP"): termos
  enviesados por sinais AI-native (`signals.bias_query`, F1.11) + as superfícies de
  descoberta do §9 (diretórios/programas/notícias). Alimenta o cohort builder (F1.14).

O planner **detecta o modo** a partir da consulta (`detect_mode`), honrando um
`discovery` declarado explicitamente pelo caller e nunca rebaixando-o.

Decisão de design (política headless — `b`/`d`): o caminho **determinista e offline**
é o **default** — o grafo roda ponta a ponta sem rede/credenciais/GPU (M2/DoD) e os
runs ficam **reprodutíveis** (ethos F2.14). A peça LLM (Nemotron-Nano, prompt
`search_planner@v1`, F0.12) é **plugável**: só refina o plano quando
`settings.planner_use_llm` está ligado **e** há `NVIDIA_API_KEY` — caindo de volta no
determinista a qualquer falha/JSON inválido. Saída **tipada** (`SearchPlan`, Pydantic)
no limite do planner; o `GraphState` (F0.5) guarda a forma achatada
(`search_terms`/`sources: list[str]`). As fontes honram a política de ToS travada
(`source_policy`/F1.15): prioriza site oficial + notícias §9.2 (allow); diretórios
proprietários §9.1 entram **só como pista de descoberta** (`api_only`), nunca os
`deny`. O viés AI-native (F1.11) é aplicado só no modo discovery (no single-company
não se força viés sobre nome próprio, conforme o prompt v1).

Tracing/custo (F2.9): o `traced_config` que este nó já passa carrega o medidor de tokens
(USAGE_RECORDER) — inócuo sem Langfuse. A chamada LLM passa pelo `cached_completion`
(F2.14): cache por prompt+modelo+`prompt_version`, hit não chega à rede.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Literal, get_args
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from packages.config import get_settings
from packages.schemas import ExecutionMode, GraphState, RunStatus
from packages.scraping.seeds import by_type
from packages.scraping.signals import bias_query

# Tipo da fonte priorizada (espelha o JSON do prompt v1 + os tipos §9 das seeds).
SourceKind = Literal[
    "official_site", "linkedin", "database", "news", "directory", "program", "search"
]
_SOURCE_KINDS: frozenset[str] = frozenset(get_args(SourceKind))

# Pistas de descoberta por setor/categoria (PT+EN): plurais/verticais e o sufixo "-tech".
# Mantidas no plural/categoria de propósito — "startup" no singular é ruído em nome próprio.
_DISCOVERY_CUES: tuple[str, ...] = (
    "startups",
    "empresas",
    "companies",
    "scaleups",
    "setor",
    "segmento",
    "mercado",
    "ecossistema",
    "vertical",
    "nicho",
    "fintechs",
    "healthtechs",
    "agtechs",
    "edtechs",
    "retailtechs",
    "insurtechs",
    "legaltechs",
    "proptechs",
    "govtechs",
    "deeptechs",
    "biotechs",
)
_DISCOVERY_RE = re.compile(r"\b(?:" + "|".join(_DISCOVERY_CUES) + r"|\w+techs)\b", re.IGNORECASE)
# URL/domínio → quase sempre uma empresa específica (single-company).
_DOMAIN_RE = re.compile(r"^(?:https?://)?[\w-]+(?:\.[\w-]+)+(?:/\S*)?$")


class PrioritizedSource(BaseModel):
    """Uma fonte priorizada do plano (§9): onde/como o scraper (F2.4) deve olhar.

    `query_or_url` é uma **URL** concreta (fonte §9 a coletar) ou um **termo de busca**
    (descoberta via Tavily, F1.1) — o scraper distingue pelo prefixo http(s).
    """

    model_config = ConfigDict(frozen=True)

    kind: SourceKind
    query_or_url: str
    rationale: str | None = None


class SearchPlan(BaseModel):
    """Plano de coleta tipado produzido pelo search_planner (F2.3)."""

    mode: ExecutionMode
    search_terms: list[str] = Field(default_factory=list)
    sources: list[PrioritizedSource] = Field(default_factory=list)
    notes: str | None = None

    @property
    def source_values(self) -> list[str]:
        """Fontes achatadas (deduped, ordem preservada) p/ `GraphState.sources` (F0.5)."""
        return _dedup(s.query_or_url for s in self.sources)


# --------------------------------------------------------------------------- modo


def detect_mode(query: str) -> ExecutionMode:
    """Heurística pura: a consulta nomeia uma empresa (single) ou um setor (discovery)?

    URL/domínio → single. Pistas de setor/categoria/plural ("fintechs", "startups",
    "-techs") → discovery. Na dúvida (nome curto, sem pistas) → single.
    """
    q = query.strip()
    if not q or _DOMAIN_RE.match(q):
        return ExecutionMode.SINGLE_COMPANY
    if _DISCOVERY_RE.search(q):
        return ExecutionMode.DISCOVERY
    return ExecutionMode.SINGLE_COMPANY


def resolve_mode(query: str, declared: ExecutionMode) -> ExecutionMode:
    """Modo efetivo: honra um `discovery` declarado; senão detecta da consulta (F2.3)."""
    if declared is ExecutionMode.DISCOVERY:
        return ExecutionMode.DISCOVERY
    return detect_mode(query)


# ----------------------------------------------------------------- planner determinista


def _dedup(items: Iterable[str]) -> list[str]:
    """Dedup preservando a ordem, descartando vazios/brancos."""
    return list(dict.fromkeys(s for s in items if s and s.strip()))


def _company_name(query: str) -> str:
    """Rótulo da empresa p/ compor termos: domínio → primeiro label do host; senão a query."""
    q = query.strip()
    if _DOMAIN_RE.match(q):
        host = urlsplit(q if "://" in q else "//" + q).hostname or q
        host = host[4:] if host.startswith("www.") else host
        return host.split(".")[0] or q
    return q


def _news_sources(limit: int = 4) -> list[PrioritizedSource]:
    """Notícias §9.2 com coleta liberada (allow) — fonte primária de cobertura (F1.15)."""
    out = [
        PrioritizedSource(kind="news", query_or_url=s.url, rationale=s.name)
        for s in by_type("news")
        if s.collectable
    ]
    return out[:limit]


def _discovery_sources(limit: int = 6) -> list[PrioritizedSource]:
    """Superfícies de descoberta §9: programas (allow) + diretórios como pista.

    Diretórios proprietários (`api_only`) entram **só como pista de descoberta** —
    não como alvo de scraping direto; os `deny` ficam de fora (F1.15 / source_policy).
    """
    out: list[PrioritizedSource] = [
        PrioritizedSource(kind="program", query_or_url=s.url, rationale=s.name)
        for s in by_type("program")
        if s.collectable
    ]
    out += [
        PrioritizedSource(kind="directory", query_or_url=s.url, rationale=s.name)
        for s in by_type("directory")
        if s.policy != "deny"
    ]
    return out[:limit]


def _single_company_plan(query: str) -> SearchPlan:
    name = _company_name(query)
    terms = _dedup([query, f"{name} startup Brasil", f"{name} site oficial"])
    sources: list[PrioritizedSource] = [
        PrioritizedSource(
            kind="official_site",
            query_or_url=f"{name} site oficial",
            rationale="Domínio oficial: produto/tech/carreiras (alto sinal, F1.11/F1.15).",
        ),
        PrioritizedSource(kind="linkedin", query_or_url=f"{name} LinkedIn empresa"),
        PrioritizedSource(kind="database", query_or_url=f"{name} Crunchbase"),
    ]
    sources += _news_sources()
    return SearchPlan(
        mode=ExecutionMode.SINGLE_COMPANY,
        search_terms=terms,
        sources=sources,
        notes="single-company: site oficial + LinkedIn + base + notícias (§9.2).",
    )


def _discovery_plan(query: str) -> SearchPlan:
    # bias_query (F1.11) devolve a query original primeiro + variantes enviesadas p/ IA.
    terms = list(bias_query(query))
    sources = _discovery_sources() + _news_sources()
    return SearchPlan(
        mode=ExecutionMode.DISCOVERY,
        search_terms=terms,
        sources=sources,
        notes="discovery: termos enviesados p/ AI-native (F1.11) + descoberta §9 (F1.14).",
    )


def deterministic_plan(query: str, mode: ExecutionMode) -> SearchPlan:
    """Plano de coleta puro/offline (default do nó) — sem rede/LLM, reprodutível."""
    if not query.strip():
        raise ValueError("query vazia")
    if mode is ExecutionMode.DISCOVERY:
        return _discovery_plan(query)
    return _single_company_plan(query)


# ------------------------------------------------------------------ refinamento LLM (opt-in)


def _json_slice(text: str) -> str:
    """Recorta do primeiro `{` ao último `}` — tolera cercas ```json``` e texto ao redor."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("sem objeto JSON na resposta do planner")
    return text[start : end + 1]


def _parse_plan(text: str, *, mode: ExecutionMode) -> SearchPlan:
    """Converte o JSON do Nano (prompt search_planner@v1) num `SearchPlan` (puro/offline).

    Tipos de fonte desconhecidos viram `search` (termo de busca genérico); itens sem
    `query_or_url` são descartados.
    """
    data = json.loads(_json_slice(text))
    terms = [str(t).strip() for t in data.get("search_terms", []) if str(t).strip()]
    sources: list[PrioritizedSource] = []
    for raw in data.get("prioritized_sources", []):
        if not isinstance(raw, dict):
            continue
        val = str(raw.get("query_or_url", "")).strip()
        if not val:
            continue
        kind = raw.get("type", "search")
        sources.append(
            PrioritizedSource(kind=kind if kind in _SOURCE_KINDS else "search", query_or_url=val)
        )
    notes = data.get("notes")
    return SearchPlan(
        mode=mode,
        search_terms=terms,
        sources=sources,
        notes=str(notes) if notes else None,
    )


def _llm_plan(query: str, mode: ExecutionMode, *, run_id: str | None = None) -> SearchPlan | None:
    """Refina o plano com o Nemotron-Nano (F0.7) + prompt versionado (F0.12). Rede.

    Degrada p/ `None` em qualquer falha (rede/JSON/validação) — o caller cai no
    determinista. Imports preguiçosos: o módulo importa offline sem langchain/Langfuse.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    from packages.observability import traced_config

    from .cache import cached_completion
    from .prompts import get_prompt

    prompt = get_prompt("search_planner")
    user = json.dumps({"query": query, "mode": mode.value}, ensure_ascii=False)
    config = traced_config(node="search_planner", prompt_version=prompt.version_tag, run_id=run_id)
    messages = [SystemMessage(content=prompt.template), HumanMessage(content=user)]
    try:
        raw = cached_completion(prompt, messages, config=config)  # cache F2.14
        plan = _parse_plan(raw, mode=mode)
    except Exception:  # noqa: BLE001 — LLM/parse falhou → fallback determinista
        return None
    return plan if (plan.search_terms or plan.sources) else None


def _merge(base: SearchPlan, llm: SearchPlan) -> SearchPlan:
    """Funde o plano do LLM com o determinista: garante a query 1ª e ancora as fontes §9.

    Termos: query (1ª, do `base`) → termos do LLM → termos do `base` (dedup). Fontes:
    LLM primeiro (intenção) ancorado pelas fontes reais do `base` (sempre presentes).
    """
    terms = _dedup([base.search_terms[0], *llm.search_terms, *base.search_terms])
    seen: set[str] = set()
    sources: list[PrioritizedSource] = []
    for src in (*llm.sources, *base.sources):
        if src.query_or_url not in seen:
            seen.add(src.query_or_url)
            sources.append(src)
    return SearchPlan(
        mode=base.mode, search_terms=terms, sources=sources, notes=llm.notes or base.notes
    )


def make_plan(query: str, mode: ExecutionMode, *, run_id: str | None = None) -> SearchPlan:
    """Plano final: determinista por padrão; refina com o Nano se ligado (F2.3)."""
    base = deterministic_plan(query, mode)
    settings = get_settings()
    if not (settings.planner_use_llm and settings.nvidia_api_key):
        return base
    llm = _llm_plan(query, mode, run_id=run_id)
    return base if llm is None else _merge(base, llm)


# ------------------------------------------------------------------------------- nó


def search_planner(state: GraphState) -> dict:
    """F2.3 — planeja termos/fontes a partir da query; marca o run como RUNNING.

    Resolve o modo (single-company vs discovery) e devolve um *update parcial* do
    `GraphState`: `mode` (modo detectado, p/ o cohort builder F1.14), `search_terms`
    e `sources` (achatadas p/ o scraper F2.4).
    """
    mode = resolve_mode(state.query, state.mode)
    plan = make_plan(state.query, mode, run_id=state.run_id)
    return {
        "status": RunStatus.RUNNING,
        "mode": mode,
        "search_terms": plan.search_terms,
        "sources": plan.source_values,
    }


__all__ = [
    "SourceKind",
    "PrioritizedSource",
    "SearchPlan",
    "detect_mode",
    "resolve_mode",
    "deterministic_plan",
    "make_plan",
    "search_planner",
]
