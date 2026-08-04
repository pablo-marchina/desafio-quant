"""Nó **classifier** (F2.6): `StartupProfile` → classe (§5.1) + `AIMIScore` (RUBRICA/F0.11).

Quarto nó do grafo (ARQUITETURA §3). Consome o perfil do extractor (F2.5) e emite o
diagnóstico de maturidade: a **classe** (`AI-native` | `AI-enabled` | `non-AI`, §5.1) e os
**4 sub-scores** do AIMI (0–25 cada) no schema `AIMIScore` (F0.5). A **definição** dos
pilares e a escala 0–25 vivem em `docs/ARQUITETURA.md §3.6` (F0.11) e são imutáveis; aqui mora
a **heurística v1** (F6.1, refina a v0 provisória de F2.6) que preenche os números — **sem
mudar** nem a definição (RUBRICA) nem o contrato de saída (`AIMIScore`).

Dois eixos que **não se confundem** (RUBRICA §6): a **classe** é o *papel* da IA (decidido
pela descrição do produto + Workflow Depth, não pelo total do AIMI) e o **AIMI** é a
*maturidade/defensabilidade* (0–100). "Wrapper" não é classe, é **região** do plano
`classe × AIMI` (`AI-native` + AIMI baixo, sobretudo P1/P3) — emerge naturalmente quando a
classe é `AI-native` mas os pilares ficam baixos.

**Regra de evidência (RUBRICA §0, princípio nº1 §8):** todo sub-score > 6 **exige** evidência
citável. A heurística cola a evidência do próprio perfil ao sub-score; sem evidência relevante,
o pilar **não passa de 6** (`MAX_SCORE_WITHOUT_EVIDENCE`) — score alto sem fonte é bloqueado,
não suposto. A faixa **"Forte/Defensável" (19–25)** só é atribuída com **corroboração** — um
sinal *forte* do pilar **e** ≥2 fontes independentes (`MIN_SOURCES_FOR_STRONG`); sem isso o teto
fica em "Estabelecido" (18, `ESTABLISHED_CEILING`). Score alto exige largura de evidência, não
suposição — a calibração final dos cortes é do eval (F6.4).

**Decisão de design (política headless b/d):** como nos nós anteriores (F2.3/F2.4/F2.5), o
caminho **determinista/offline é o default** — a heurística v1 pontua a partir dos sinais
estruturados do perfil **sem rede/LLM/GPU**, deixando os runs reprodutíveis (ethos F2.14). A
peça LLM (Nemotron-Super, reasoning ON — `classifier@v1`, F0.12) é **plugável** atrás de
`settings.classifier_use_llm` + chave **ou** de um adapter `classify=` injetado (testes/worker
F2.10), **caindo de volta na heurística** a qualquer falha de rede/JSON/validação. Sem perfil
(espinha offline sem extração), o nó é um **no-op limpo** (`{}`, `aimi` fica `None`) — grafo
verde ponta a ponta (M2/DoD) sem alucinar um score sem entrada.

Hooks de tasks futuras: evidence_validator (F2.7) confere a regra de N fontes sobre o `aimi`;
o recommender (F4) usa os gaps (P3 baixo = gatilho); o Inception Priority (F6.13) deriva do
AIMI; os caminhos terminais (F2.12 dados insuficientes, F2.13 non-AI fora de escopo) leem a
classe/confiança daqui.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

from packages.config import get_settings
from packages.schemas import (
    MAX_SCORE_WITHOUT_EVIDENCE,
    AIMIPillar,
    AIMIScore,
    Classification,
    Evidence,
    GraphState,
    PillarScore,
    StartupProfile,
)
from packages.scraping.provenance import make_snippet
from packages.scraping.source_policy import annotate as source_policy_for

from .inception import inception_priority

# Adapter de classificação injetável: profile -> JSON cru do modelo. Default = Nemotron-Super.
ClassifyFn = Callable[[StartupProfile], str]

#: Teto da faixa "Estabelecido" (RUBRICA §1). A heurística v1 só ultrapassa (→ "Forte/Defensável",
#: 19–25) com **corroboração**: sinal forte do pilar + ≥ `MIN_SOURCES_FOR_STRONG` fontes
#: independentes. Sem isso o sub-score trava aqui — score alto exige largura de evidência, não
#: suposição. A escala 0–25 do schema permanece intacta (calibração dos cortes no eval, F6.4).
ESTABLISHED_CEILING = 18
STRONG_BAND_FLOOR = 19
MIN_SOURCES_FOR_STRONG = 2

#: Piso de confiança p/ o terminal **"non-AI fora de escopo" (F2.13)**: abaixo disto a classe
#: `non-AI` não é firme o bastante p/ descartar a empresa — o run segue o caminho normal. A
#: *corroboração* (≥ N fontes independentes) é exigida à parte pelo evidence_validator (F2.7);
#: juntas significam "há base p/ dizer, com confiança, que não é alvo Inception". Calibração
#: final no eval (F6.4); a v0 sempre emite `confidence` (o caminho LLM pode omitir → não-firme).
NON_AI_CONFIDENCE_FLOOR = 0.5


# --------------------------------------------------------------- léxico de sinais (v0)

# Tokens curtos/ambíguos casados com borda de palavra (evita "ia" em "média", "ai" em "mail").
_BOUNDED: frozenset[str] = frozenset(
    {"ia", "ai", "ml", "rag", "gpu", "nim", "nlp", "gtm", "rpa", "lora", "peft", "gpt"}
)

# IA presente no produto (classificação): núcleo vs periférico.
AI_TERMS: tuple[str, ...] = (
    "ia", "ai", "ml", "llm", "genai", "inteligência artificial", "inteligencia artificial",
    "artificial intelligence", "machine learning", "aprendizado de máquina", "deep learning",
    "rede neural", "redes neurais", "neural", "modelo de linguagem", "modelos de linguagem",
    "generativa", "generativo", "generative", "nlp", "visão computacional", "computer vision",
    "agente", "agentes", "agent", "agents", "copilot", "gpt", "embedding", "embeddings", "rag",
)

# P2 — Workflow Depth: automação multi-passo, agentes, integrações.
WORKFLOW_TERMS: tuple[str, ...] = (
    "workflow", "fluxo de trabalho", "automação", "automation", "automatiza", "orquestra",
    "orchestration", "orchestrate", "pipeline", "integra", "integração", "integration",
    "multi-step", "multi-passo", "multiagente", "multi-agente", "end-to-end", "ponta a ponta",
    "rpa", "agente", "agentes", "agent", "agents",
)

# P3 — Technical Optimization: stack de inferência própria (sobe o pilar).
OPT_TERMS: tuple[str, ...] = (
    "fine-tun", "fine tuning", "ajuste fino", "quantiz", "serving", "inferência própria",
    "self-host", "self host", "on-premise", "on-prem", "triton", "tensorrt", "tensor-rt",
    "vllm", "nim", "rapids", "cuda", "gpu", "modelo próprio", "modelos próprios", "lora",
    "peft", "batching", "kv cache", "kv-cache", "destila", "destilação",
)

# P3 — dependência de API crua (mantém o pilar baixo = gatilho de graduação, RUBRICA §4).
API_TERMS: tuple[str, ...] = (
    "openai", "anthropic", "gpt-4", "gpt-3", "claude", "gemini", "via api", "chamadas de api",
    "wrapper",
)

# P1 — Data Moat: dado proprietário + feedback loop.
DATA_TERMS: tuple[str, ...] = (
    "dados proprietários", "dados proprietarios", "proprietary data", "dado proprietário",
    "feedback loop", "loop de feedback", "rotulagem", "rotulação", "labeling",
    "dataset proprietário", "dataset proprietario", "dados próprios", "dados proprios",
    "fine-tun", "treinado com dados", "data moat", "ativo de dados",
)

# P4 — Distribution & Moat: GTM, enterprise, lock-in (textual; sinais estruturados à parte).
DIST_TERMS: tuple[str, ...] = (
    "enterprise", "corporativo", "lock-in", "contrato", "parceria", "parcerias",
    "go-to-market", "gtm", "white label", "white-label", "marketplace", "api pública",
    "integração enterprise",
)

# Sinais **fortes** por pilar (subconjunto dos termos acima): denotam capacidade real/defensável,
# não só menção. Na v1 cada sinal forte soma profundidade ao score e, com corroboração (≥2 fontes),
# habilita a faixa "Forte/Defensável" (19–25). Termos genéricos/de apoio (ex.: "gpu", "cuda",
# "marketplace") ficam de fora — sustentam "Emergente/Estabelecido", não "Forte" sozinhos.
DATA_STRONG: frozenset[str] = frozenset(
    {
        "dados proprietários", "dados proprietarios", "proprietary data", "dado proprietário",
        "feedback loop", "loop de feedback", "dataset proprietário", "dataset proprietario",
        "dados próprios", "dados proprios", "data moat", "ativo de dados", "fine-tun",
        "treinado com dados",
    }
)
WORKFLOW_STRONG: frozenset[str] = frozenset(
    {
        "end-to-end", "ponta a ponta", "multiagente", "multi-agente", "orquestra",
        "orchestration", "orchestrate",
    }
)
OPT_STRONG: frozenset[str] = frozenset(
    {
        "fine-tun", "fine tuning", "ajuste fino", "serving", "inferência própria", "self-host",
        "self host", "on-premise", "on-prem", "triton", "tensorrt", "tensor-rt", "vllm", "nim",
        "rapids", "modelo próprio", "modelos próprios", "lora", "peft", "quantiz", "destila",
        "destilação",
    }
)
DIST_STRONG: frozenset[str] = frozenset(
    {"enterprise", "lock-in", "contrato", "integração enterprise"}
)


# --------------------------------------------------------------------------- helpers puros


def _matches(low: str, term: str) -> bool:
    """`term` ocorre em `low`? Tokens curtos ambíguos exigem borda de palavra."""
    if term in _BOUNDED:
        return re.search(rf"\b{re.escape(term)}\b", low) is not None
    return term in low


def _dedup_ev(evidence: Iterable[Evidence]) -> list[Evidence]:
    """Dedup de evidências por (url, snippet), preservando a ordem."""
    seen: set[tuple[str, str]] = set()
    out: list[Evidence] = []
    for ev in evidence:
        key = (str(ev.url), ev.snippet)
        if key not in seen:
            seen.add(key)
            out.append(ev)
    return out


def _scan(
    sources: Sequence[tuple[str, list[Evidence]]], terms: tuple[str, ...]
) -> tuple[set[str], list[Evidence]]:
    """Varre (texto, evidência) por `terms`: devolve sinais distintos + evidência que os ancora.

    A evidência de uma fonte só entra se **algum** termo casou nela — assim o sub-score só
    sobe acompanhado da fonte que o sustenta (RUBRICA §0).
    """
    matched: set[str] = set()
    evidence: list[Evidence] = []
    for text, ev in sources:
        low = text.lower()
        local = {t for t in terms if _matches(low, t)}
        if local:
            matched |= local
            evidence.extend(ev)
    return matched, _dedup_ev(evidence)


def _claim_src(claim: Any) -> list[tuple[str, list[Evidence]]]:
    """Fonte (texto, evidência) de um `Claim` escalar do perfil; vazio se ausente."""
    if claim is None:
        return []
    return [(str(claim.value), list(claim.evidence))]


def _items_src(items: Sequence[Any], fields: tuple[str, ...]) -> list[tuple[str, list[Evidence]]]:
    """Fontes (texto concatenado dos `fields`, evidência) de uma coleção do perfil."""
    out: list[tuple[str, list[Evidence]]] = []
    for it in items:
        text = " ".join(str(getattr(it, f) or "") for f in fields)
        out.append((text, list(it.evidence)))
    return out


def _funding_src(profile: StartupProfile) -> list[tuple[str, list[Evidence]]]:
    """Fonte (texto, evidência) do bloco de funding (estágio + investidores)."""
    f = profile.funding
    if f is None:
        return []
    text = " ".join([f.last_round_stage or "", *f.investors])
    return [(text, list(f.evidence))]


def _collect_evidence(items: Sequence[Any]) -> list[Evidence]:
    """Achata a evidência de uma coleção de itens (clientes/produtos/...)."""
    out: list[Evidence] = []
    for it in items:
        out.extend(it.evidence)
    return _dedup_ev(out)


def _strong_count(signals: set[str], strong: frozenset[str]) -> int:
    """Quantos dos sinais casados são **fortes** (subconjunto que denota capacidade real)."""
    return len(signals & strong)


def _n_sources(evidence: Iterable[Evidence]) -> int:
    """Nº de fontes **independentes** (URLs distintas) que ancoram o pilar — mede corroboração."""
    return len({str(e.url) for e in evidence})


def _band_score(
    distinct: int, strong: int, n_sources: int, *, has_evidence: bool, boost: int = 0
) -> tuple[int, str]:
    """Sinais → `(score 0–25, breakdown)` (heurística **v1**); sem evidência, trava em ≤6.

    *Breadth* (sinais distintos) dá a base — 0 → 3 (ausente) · 1 → 9 · 2 → 12 (emergente) · 3+ →
    15 (estabelecido); cada sinal **forte** soma profundidade (+2) e `boost` (sinais estruturados)
    entra por cima. A faixa **"Forte/Defensável" (19–25)** só é alcançável com **corroboração** —
    ao menos um sinal forte **e** ≥ `MIN_SOURCES_FOR_STRONG` fontes independentes (RUBRICA §0/§1);
    sem isso o teto é `ESTABLISHED_CEILING` (18). A trava de evidência (RUBRICA §0) é aplicada por
    último — o validator de `PillarScore` a reforça.

    **Explicabilidade (F6.2):** além do número, devolve um `breakdown` determinístico — os fatores
    que compõem o sub-score (base + profundidade + boost) e qual teto, se algum, o limitou. É a
    mesma conta que produz o `score`, em texto auditável: alimenta a `justificativa` do pilar (UI
    F5.4/F5.5, briefing) e os "fatores" exigidos pelo Inception Priority (F6.13).
    """
    base = {0: 3, 1: 9, 2: 12}.get(distinct, 15)
    raw = base + boost + 2 * strong
    parts = [f"base {base} ({distinct} sinal(is))"]
    if strong:
        parts.append(f"+{2 * strong} profundidade ({strong} forte(s))")
    if boost:
        parts.append(f"+{boost} tração/contexto")
    cap = ""
    corroborated = strong >= 1 and n_sources >= MIN_SOURCES_FOR_STRONG
    # Sem corroboração (sinal forte + fontes independentes), não cruza para "Forte/Defensável".
    if not corroborated:
        if raw > ESTABLISHED_CEILING:
            cap = f"teto Estabelecido {ESTABLISHED_CEILING} (sem corroboração: " \
                f"{strong} forte × {n_sources} fonte(s))"
        raw = min(raw, ESTABLISHED_CEILING)
    elif raw >= STRONG_BAND_FLOOR:
        cap = f"faixa Forte liberada (corroboração: {strong} forte × {n_sources} fontes)"
    raw = max(0, min(25, raw))
    if not has_evidence:
        if raw > MAX_SCORE_WITHOUT_EVIDENCE:
            cap = f"teto sem evidência {MAX_SCORE_WITHOUT_EVIDENCE} (RUBRICA §0)"
        raw = min(raw, MAX_SCORE_WITHOUT_EVIDENCE)
    breakdown = " ".join(parts) + f" = {raw}" + (f"; {cap}" if cap else "")
    return raw, breakdown


def _justify(label: str, signals: set[str], *, extra: str = "", breakdown: str = "") -> str:
    """Justificativa curta do pilar citando os sinais que pesaram (auditável).

    Quando `breakdown` (F6.2) é dado, anexa o cálculo do sub-score — o número deixa de ser
    caixa-preta: lê-se *quais* sinais pesaram **e** *como* viraram o score.
    """
    if signals:
        base = f"Sinais de {label}: {', '.join(sorted(signals))}."
    else:
        base = f"Sem sinais públicos claros de {label} no perfil."
    calc = f"Cálculo: {breakdown}." if breakdown else ""
    return " ".join(p for p in (base, extra, calc) if p).strip()


# ----------------------------------------------------------------- heurística v0 por pilar


def _pillar_data_moat(profile: StartupProfile) -> PillarScore:
    src = (
        _claim_src(profile.descricao)
        + _items_src(profile.tecnologias, ("nome", "categoria", "uso"))
        + _items_src(profile.clientes, ("nome", "segmento"))
    )
    signals, evidence = _scan(src, DATA_TERMS)
    # Boost modesto: muitos clientes ⇒ potencial de dado de uso (só se houver evidência deles).
    client_ev = _collect_evidence(profile.clientes)
    boost = 0
    extra = ""
    if len(profile.clientes) >= 3 and client_ev:
        boost = 3
        evidence = _dedup_ev([*evidence, *client_ev])
        extra = f"{len(profile.clientes)} clientes (potencial de dado de uso)."
    score, breakdown = _band_score(
        len(signals), _strong_count(signals, DATA_STRONG), _n_sources(evidence),
        has_evidence=bool(evidence), boost=boost,
    )
    return PillarScore(
        pilar=AIMIPillar.DATA_MOAT,
        score=score,
        justificativa=_justify(
            "dado proprietário/feedback loop", signals, extra=extra, breakdown=breakdown
        ),
        evidencia=evidence,
    )


def _pillar_workflow_depth(profile: StartupProfile) -> PillarScore:
    src = (
        _claim_src(profile.descricao)
        + _items_src(profile.produtos, ("nome", "descricao", "categoria"))
        + _items_src(profile.tecnologias, ("nome", "categoria", "uso"))
    )
    signals, evidence = _scan(src, WORKFLOW_TERMS)
    score, breakdown = _band_score(
        len(signals), _strong_count(signals, WORKFLOW_STRONG), _n_sources(evidence),
        has_evidence=bool(evidence),
    )
    return PillarScore(
        pilar=AIMIPillar.WORKFLOW_DEPTH,
        score=score,
        justificativa=_justify("workflow/automação multi-passo", signals, breakdown=breakdown),
        evidencia=evidence,
    )


def _pillar_technical_optimization(profile: StartupProfile) -> PillarScore:
    src = _claim_src(profile.descricao) + _items_src(
        profile.tecnologias, ("nome", "categoria", "uso")
    )
    opt_signals, opt_ev = _scan(src, OPT_TERMS)
    api_signals, _ = _scan(src, API_TERMS)
    score, breakdown = _band_score(
        len(opt_signals), _strong_count(opt_signals, OPT_STRONG), _n_sources(opt_ev),
        has_evidence=bool(opt_ev),
    )
    extra = ""
    # 100% API externa, sem sinal de otimização própria → pilar baixo = gatilho (RUBRICA §4).
    if not opt_signals and api_signals:
        score = min(score, MAX_SCORE_WITHOUT_EVIDENCE)
        extra = (
            f"Dependência de API externa ({', '.join(sorted(api_signals))}) "
            "sem stack própria — alvo de graduação."
        )
    return PillarScore(
        pilar=AIMIPillar.TECHNICAL_OPTIMIZATION,
        score=score,
        justificativa=_justify(
            "stack de inferência própria", opt_signals, extra=extra, breakdown=breakdown
        ),
        evidencia=opt_ev,
    )


def _pillar_distribution_moat(profile: StartupProfile) -> PillarScore:
    src = (
        _claim_src(profile.descricao)
        + _items_src(profile.clientes, ("nome", "segmento"))
        + _funding_src(profile)
    )
    signals, evidence = _scan(src, DIST_TERMS)
    client_ev = _collect_evidence(profile.clientes)
    fund_ev = _dedup_ev(profile.funding.evidence) if profile.funding else []
    boost = 0
    extras: list[str] = []
    if any(c.enterprise for c in profile.clientes) and client_ev:
        boost += 4
        extras.append("clientes enterprise")
    elif profile.clientes and client_ev:
        boost += 2
        extras.append(f"{len(profile.clientes)} cliente(s) público(s)")
    f = profile.funding
    if f is not None and (f.total_raised_usd or f.investors) and fund_ev:
        boost += 2
        extras.append("captação divulgada")
    evidence = _dedup_ev([*evidence, *client_ev, *fund_ev]) if boost else evidence
    score, breakdown = _band_score(
        len(signals), _strong_count(signals, DIST_STRONG), _n_sources(evidence),
        has_evidence=bool(evidence), boost=boost,
    )
    extra = ("Tração: " + ", ".join(extras) + ".") if extras else ""
    return PillarScore(
        pilar=AIMIPillar.DISTRIBUTION_MOAT,
        score=score,
        justificativa=_justify(
            "distribuição/defensabilidade", signals, extra=extra, breakdown=breakdown
        ),
        evidencia=evidence,
    )


def _classify_class(profile: StartupProfile, workflow_score: int) -> Classification:
    """Classe (§5.1) pelo *papel* da IA, não pelo total (RUBRICA §6).

    Sem qualquer sinal de IA → `non-AI`. Com IA **no núcleo** (descrição/produtos) e Workflow
    Depth acima da faixa rasa (>8, RUBRICA §6) → `AI-native` (um wrapper continua AI-native,
    só com AIMI baixo). Caso contrário (IA periférica / workflow raso) → `AI-enabled`.
    """
    anywhere = (
        _claim_src(profile.descricao)
        + _claim_src(profile.setor)
        + _items_src(profile.produtos, ("nome", "descricao", "categoria"))
        + _items_src(profile.tecnologias, ("nome", "categoria", "uso"))
    )
    if not _scan(anywhere, AI_TERMS)[0]:
        return Classification.NON_AI
    core = _claim_src(profile.descricao) + _items_src(
        profile.produtos, ("nome", "descricao", "categoria")
    )
    is_core = bool(_scan(core, AI_TERMS)[0])
    if is_core and workflow_score > 8:
        return Classification.AI_NATIVE
    return Classification.AI_ENABLED


def _confidence(profile: StartupProfile) -> float:
    """Confiança da v0 pela riqueza do perfil (nº de fontes + dimensões preenchidas)."""
    n_sources = len({str(u) for u in profile.source_urls}) or len(
        {str(e.url) for e in profile.all_evidence}
    )
    n_fields = sum(
        bool(x)
        for x in (
            profile.descricao,
            profile.setor,
            profile.produtos,
            profile.tecnologias,
            profile.clientes,
            profile.funding,
        )
    )
    return round(min(1.0, 0.2 + 0.1 * n_sources + 0.05 * n_fields), 2)


def heuristic_score(profile: StartupProfile) -> AIMIScore:
    """Heurística AIMI **v1** (default determinista/offline): perfil → `AIMIScore`.

    Refina a v0 provisória (F2.6): além da *breadth* de sinais, pesa sinais **fortes** e exige
    **corroboração** (sinal forte + ≥2 fontes) p/ a faixa "Forte/Defensável" (RUBRICA §0/§1).
    Pontua os 4 pilares pela RUBRICA (F0.11) a partir dos sinais estruturados do perfil, com
    evidência colada a cada sub-score, e deriva a classe (§5.1). Cada sub-score é **explicável**
    (F6.2): a `justificativa` carrega os sinais que pesaram **e** o cálculo (base + profundidade +
    boost + teto aplicado) — o número nunca é caixa-preta. Pura/reprodutível — sem rede/LLM.
    `total`/`band` são recomputados pelo validator do `AIMIScore`.
    """
    p1 = _pillar_data_moat(profile)
    p2 = _pillar_workflow_depth(profile)
    p3 = _pillar_technical_optimization(profile)
    p4 = _pillar_distribution_moat(profile)
    aimi = AIMIScore(
        data_moat=p1,
        workflow_depth=p2,
        technical_optimization=p3,
        distribution_moat=p4,
        classificacao=_classify_class(profile, p2.score),
        confidence=_confidence(profile),
        heuristic_version="v1",
    )
    # F6.13 — fila de outreach: potencial AI-native × upside NVIDIA, derivado do próprio AIMI.
    aimi.inception_priority = inception_priority(aimi)[0]
    return aimi


# ------------------------------------------------------------------ caminho LLM (opt-in)


def _json_slice(text: str) -> str:
    """Recorta do primeiro `{` ao último `}` — tolera cercas ```json``` e texto ao redor."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("sem objeto JSON na resposta do classifier")
    return text[start : end + 1]


def _norm_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


_CLASS_ALIASES: dict[str, Classification] = {
    "ai_native": Classification.AI_NATIVE,
    "ai-native": Classification.AI_NATIVE,
    "ai_enabled": Classification.AI_ENABLED,
    "ai-enabled": Classification.AI_ENABLED,
    "non_ai": Classification.NON_AI,
    "non-ai": Classification.NON_AI,
}


def _parse_class(value: Any) -> Classification:
    """Normaliza a classe vinda do modelo (aceita snake/kebab/maiúsculas)."""
    key = str(value).strip().lower()
    if key in _CLASS_ALIASES:
        return _CLASS_ALIASES[key]
    raise ValueError(f"classe desconhecida do classifier: {value!r}")


def _clamp_conf(value: Any) -> float | None:
    try:
        c = float(value)
    except (TypeError, ValueError):
        return None
    return min(1.0, max(0.0, c))


def _evidence_from_profile(raw: Any, index: dict[str, Evidence]) -> list[Evidence]:
    """Ancora a evidência citada pelo modelo na proveniência **real** do perfil (F1.9).

    Quando a url citada já está no perfil, reusa a `Evidence` existente (fetched_at/hash/policy
    reais); senão constrói uma com a política de ToS (F1.15) e instante do registro. Item sem
    url/trecho é descartado (sem fonte não há evidência).
    """
    out: list[Evidence] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        if not url:
            continue
        existing = index.get(_norm_url(url))
        if existing is not None:
            out.append(existing)
            continue
        if not snippet:
            continue
        try:
            out.append(
                Evidence(
                    url=url,
                    snippet=make_snippet(snippet),
                    fetched_at=datetime.now(UTC),
                    source_policy=source_policy_for(url),
                )
            )
        except Exception:  # noqa: BLE001 — url inválida p/ Evidence → descarta sem derrubar
            continue
    return _dedup_ev(out)


def parse_score(text: str, *, profile: StartupProfile) -> AIMIScore:
    """Converte o JSON do Super (prompt classifier@v1) num `AIMIScore` ancorado no perfil.

    Tolerante (no padrão dos demais parsers F2): sub-score saneado p/ [0,25]; sub-score > 6 sem
    evidência citável é rebaixado a 6 (RUBRICA §0) mesmo que o modelo não cite. A evidência é
    ancorada na proveniência real do perfil (não no que o modelo alegar).
    """
    data = json.loads(_json_slice(text))
    if not isinstance(data, dict):
        raise ValueError("JSON do classifier não é um objeto")
    index = {_norm_url(str(e.url)): e for e in profile.all_evidence}

    def pillar(key: str, pilar: AIMIPillar) -> PillarScore:
        raw = data.get(key) if isinstance(data.get(key), dict) else {}
        try:
            score = int(raw.get("score", 0))
        except (TypeError, ValueError):
            score = 0
        score = max(0, min(25, score))
        evidence = _evidence_from_profile(raw.get("evidence", []), index)
        if score > MAX_SCORE_WITHOUT_EVIDENCE and not evidence:
            score = MAX_SCORE_WITHOUT_EVIDENCE
        return PillarScore(
            pilar=pilar,
            score=score,
            justificativa=str(raw.get("justificativa", "")).strip() or "(sem justificativa)",
            evidencia=evidence,
        )

    aimi = AIMIScore(
        data_moat=pillar("data_moat", AIMIPillar.DATA_MOAT),
        workflow_depth=pillar("workflow_depth", AIMIPillar.WORKFLOW_DEPTH),
        technical_optimization=pillar("technical_optimization", AIMIPillar.TECHNICAL_OPTIMIZATION),
        distribution_moat=pillar("distribution_moat", AIMIPillar.DISTRIBUTION_MOAT),
        classificacao=_parse_class(data.get("classificacao", data.get("classe"))),
        confidence=_clamp_conf(data.get("confidence")),
        heuristic_version="v1",
    )
    # F6.13 — Inception Priority também no caminho LLM (deriva do AIMI, não do que o modelo alegar).
    aimi.inception_priority = inception_priority(aimi)[0]
    return aimi


def classify_with_llm(profile: StartupProfile, *, classify: ClassifyFn) -> AIMIScore | None:
    """Roda o adapter de classificação e tipa a saída; **degrada p/ `None`** em qualquer falha.

    Núcleo testável do caminho LLM: o adapter (fake nos testes, Nemotron-Super em produção)
    devolve o JSON cru; aqui só parse + tipagem ancorada no perfil. Erro de rede/JSON/validação
    vira `None` → o caller cai na heurística v0 (não alucina).
    """
    try:
        raw = classify(profile)
        return parse_score(raw, profile=profile)
    except Exception:  # noqa: BLE001 — LLM/parse/validação falhou → fallback à heurística
        return None


def _default_classify(profile: StartupProfile, *, run_id: str | None = None) -> str:
    """Adapter real: Nemotron-Super (reasoning ON, F0.7) + prompt versionado (F0.12). Rede.

    Imports preguiçosos: o módulo importa offline sem langchain/Langfuse. O `prompt.model`
    (`reason`) escolhe o Super; `reasoning_system_message` liga o raciocínio conforme o
    frontmatter; `traced_config` carimba o `version_tag` no trace (F0.8) sem exigir Langfuse.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    from packages.observability import traced_config

    from .cache import cached_completion
    from .llm import reasoning_system_message
    from .prompts import get_prompt

    prompt = get_prompt("classifier")
    config = traced_config(node="classifier", prompt_version=prompt.version_tag, run_id=run_id)
    payload = json.dumps(profile.model_dump(mode="json"), ensure_ascii=False)
    messages: list = []
    if prompt.reasoning:
        messages.append(reasoning_system_message(True))
    messages.append(SystemMessage(content=prompt.template))
    messages.append(HumanMessage(content=payload))
    return cached_completion(prompt, messages, config=config)  # cache F2.14


def make_aimi(
    profile: StartupProfile,
    *,
    classify: ClassifyFn | None = None,
    run_id: str | None = None,
) -> AIMIScore:
    """AIMI final: heurística v0 por padrão; usa o Super se ligado, com fallback à v0 (F2.6)."""
    base = heuristic_score(profile)
    if classify is None and not get_settings().classifier_use_llm:
        return base  # default determinista/offline (reproduzível)
    adapter: ClassifyFn = classify or (lambda p: _default_classify(p, run_id=run_id))
    llm = classify_with_llm(profile, classify=adapter)
    return llm if llm is not None else base


# --------------------------------------------------------- veredito terminal (lido por F2.13)


def is_confident_non_ai(aimi: AIMIScore | None) -> bool:
    """A startup foi classificada **`non-AI` com confiança** (F2.13)?

    `True` só quando há diagnóstico (`aimi`), a classe é `non-AI` e a confiança da classificação
    atinge `NON_AI_CONFIDENCE_FLOOR`. Confiança ausente (`None`, possível no caminho LLM) conta
    como **não-firme** — sem sinal de confiança não se descarta a empresa. A *largura* da
    evidência (≥ N fontes independentes) é checada à parte pelo evidence_validator (F2.7): só no
    ramo já corroborado este veredito vira o terminal "fora de escopo" — assim "fora de escopo"
    (non-AI confiante) nunca se confunde com "dados insuficientes" (F2.12).
    """
    if aimi is None or aimi.classificacao is not Classification.NON_AI:
        return False
    return aimi.confidence is not None and aimi.confidence >= NON_AI_CONFIDENCE_FLOOR


# ------------------------------------------------------------------------------- nó


def classifier(state: GraphState, *, classify: ClassifyFn | None = None) -> dict:
    """F2.6 — diagnostica classe (§5.1) + AIMI (RUBRICA/F0.11); devolve update parcial.

    Sem `profile` (espinha offline sem extração) é um no-op limpo (`{}`) — `aimi` fica `None`,
    grafo verde ponta a ponta (M2/DoD) sem alucinar score. Com perfil, pontua pela heurística
    v0 (default determinista) ou pelo Super se ligado (`settings.classifier_use_llm`/`classify=`),
    com fallback à v0 a qualquer falha. A suficiência de evidência fica para o evidence_validator
    (F2.7); aqui só se produz o diagnóstico tipado.
    """
    profile = state.profile
    if profile is None:
        return {}  # nada a classificar (offline default) → aimi None, espinha verde (M2)
    return {"aimi": make_aimi(profile, classify=classify, run_id=state.run_id)}


__all__ = [
    "ClassifyFn",
    "NON_AI_CONFIDENCE_FLOOR",
    "heuristic_score",
    "parse_score",
    "classify_with_llm",
    "make_aimi",
    "is_confident_non_ai",
    "classifier",
]
