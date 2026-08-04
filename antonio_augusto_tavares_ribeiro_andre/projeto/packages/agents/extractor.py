"""Nó **extractor** (F2.5): `raw_docs` → `StartupProfile` estruturado, com proveniência.

Terceiro nó do grafo (ARQUITETURA §3). Consome os documentos brutos do scraper (F2.4)
e produz o `StartupProfile` (F0.5) que o classifier/AIMI (F2.6) vai pontuar — cobrindo
as dimensões do §2 (empresa, produto, setor, clientes, funding, founders, tecnologias).
É aqui que o **princípio nº1** (ARQUITETURA §8) se materializa: **cada campo carrega a
evidência que o sustenta** (`Claim`/`Evidence`, F0.5) — nada é afirmado sem fonte citável.

A proveniência (`fetched_at` + `content_hash` + `source_policy`) **não** é confiada ao
LLM: o que o modelo cita é o par (`url`, trecho); o resto é **derivado dos `raw_docs`**
(o instante/hash reais da coleta, F1.9) e da política de ToS travada (F1.15,
`source_policy.annotate`). Assim a evidência é auditável mesmo que o modelo erre datas, e
o snippet é normalizado/limitado por `make_snippet` (cita, não copia a página).

**Decisão de design (política headless b/d):** como no search_planner (F2.3) e no scraper
(F2.4), **offline é o default** — sem `raw_docs` (espinha sem rede) **ou** com o LLM
desligado, o nó é um no-op limpo (`{}`, `profile` fica `None`), mantendo o grafo verde
ponta a ponta (M2/DoD "grafo end-to-end" / `test_graph`) e os runs reprodutíveis (ethos
F2.14). A peça LLM (Nemotron-Super, reasoning ON — `extractor@v1`, F0.12) é **plugável**:
liga com `settings.extractor_use_llm` + `NVIDIA_API_KEY`, **ou** injetando um adapter
`extract=` (é como os testes exercitam o parse/proveniência sem rede e o worker F2.10
liga a extração real). Saída **tipada** no limite do nó (`StartupProfile`, Pydantic); a
não-extração **degrada** sem alucinar (perfil fica `None`, erro rastreável em `errors`) —
a suficiência de evidência é decidida adiante pelo evidence_validator (regra de N fontes,
F2.7), não aqui.

A **persistência** (tabelas `company`/`founder`/`evidence`, F0.6/F1.10) é o caminho que o
scraper (F2.4) anota como dele: aqui ela é um **hook injetável** (`persist=`) desligado por
padrão — o backbone offline não toca o banco; o worker (F2.10) injeta um callable que liga
o `persist_profile` (F1.10, com dedup CNPJ>domínio>nome e escopo BR) a uma `Session`.

Hooks de tasks futuras: classifier/AIMI (F2.6) lê `profile`; evidence_validator (F2.7)
conta fontes do perfil; o roteamento OUT_OF_SCOPE (F2.13) usa o `br_scope` da persistência.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import HttpUrl as _HttpUrl
from pydantic import TypeAdapter, ValidationError

from packages.config import get_settings
from packages.schemas import GraphState, RawDocument
from packages.schemas.evidence import Claim, Evidence
from packages.schemas.profile import (
    Customer,
    Founder,
    Funding,
    Product,
    StartupProfile,
    Technology,
)
from packages.scraping.provenance import make_snippet
from packages.scraping.source_policy import annotate as source_policy_for

logger = logging.getLogger(__name__)

# Adapter de extração injetável: (query, docs) -> JSON cru do modelo. Default = Nemotron-Super.
ExtractFn = Callable[[str, "Sequence[RawDocument]"], str]

# Orçamento de conteúdo enviado ao modelo (free tier build.nvidia.com / F2.11). Caps **deliberados**
# p/ manter a chamada do Super sob o teto de 120s (F7.6): payload grande × reasoning ON estourava o
# timeout (diag 2026-06-13: Tractian/BotCity com ~20–28k chars). Os docs vêm em ordem de prioridade
# (site oficial primeiro), então capar nº de docs + chars/doc preserva o sinal e poda a cauda de
# agregadores. 6 docs × 4000 ≈ 24k no pior caso.
DEFAULT_DOC_CHARS = 4000
DEFAULT_MAX_DOCS = 6

# Validador de URL reutilizável (não constrói modelo por chamada).
_URL_ADAPTER: TypeAdapter[_HttpUrl] = TypeAdapter(_HttpUrl)


# --------------------------------------------------------------------------- helpers puros


def _maybe_url(value: Any) -> str | None:
    """Devolve a string só se for uma URL http(s) válida; senão `None` (não derruba)."""
    if not value or not isinstance(value, str):
        return None
    try:
        _URL_ADAPTER.validate_python(value.strip())
    except ValidationError:
        return None
    return value.strip()


def _loads_json_object(text: str) -> dict:
    """Primeiro objeto JSON do texto, tipado como `dict`.

    Tolera cercas ```json```/prosa **antes** (pula até o 1º `{`) e — diferença vs. o recorte
    ingênuo `{`…`}` — **lixo depois**: o Super às vezes emite o objeto seguido de explicação ou
    um 2º objeto (diag 2026-06-13: Birdie quebrava com `JSONDecodeError: Extra data`). `raw_decode`
    para no fim do 1º objeto e ignora o resto, em vez de `json.loads` engasgar no excedente.
    """
    start = text.find("{")
    if start == -1:
        raise ValueError("sem objeto JSON na resposta do extractor")
    try:
        obj, _ = json.JSONDecoder().raw_decode(text, start)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON do extractor inválido: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError("JSON do extractor não é um objeto")
    return obj


def _doc_index(docs: Sequence[RawDocument]) -> dict[str, RawDocument]:
    """Índice url-normalizada → doc, p/ ancorar a proveniência real (F1.9) na evidência."""
    index: dict[str, RawDocument] = {}
    for doc in docs:
        index.setdefault(_norm_url(str(doc.url)), doc)
    return index


def _norm_url(url: str) -> str:
    """Normalização leve p/ casar a url citada pelo modelo com a coletada (sem barra final)."""
    return url.strip().rstrip("/").lower()


def _clamp_conf(value: Any) -> float | None:
    """Confiança da extração saneada p/ [0,1]; valor inválido vira `None` (não derruba)."""
    try:
        c = float(value)
    except (TypeError, ValueError):
        return None
    return min(1.0, max(0.0, c))


def _evidence(raw: Any, index: dict[str, RawDocument]) -> list[Evidence]:
    """Constrói a evidência citável: o modelo dá (url, snippet); o resto vem dos docs.

    `fetched_at`/`content_hash` saem do `raw_doc` casado (proveniência real, F1.9), com
    fallback p/ o instante do registro quando a url citada não está entre as coletadas;
    `source_policy` sempre da política de ToS travada (F1.15). Item sem url válida ou sem
    trecho é descartado (sem fonte não há evidência).
    """
    out: list[Evidence] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        url = _maybe_url(item.get("url"))
        snippet = str(item.get("snippet", "")).strip()
        if not url or not snippet:
            continue
        doc = index.get(_norm_url(url))
        try:
            out.append(
                Evidence(
                    url=url,
                    snippet=make_snippet(snippet),
                    fetched_at=doc.fetched_at if doc else datetime.now(UTC),
                    content_hash=doc.content_hash if doc else None,
                    source_title=str(item["source_title"]).strip()
                    if item.get("source_title")
                    else None,
                    source_policy=source_policy_for(url),
                )
            )
        except ValidationError:
            continue  # url/campos inválidos p/ Evidence → descarta sem derrubar
    return out


def _unwrap(raw: Any) -> tuple[Any, Any, float | None]:
    """Aceita valor cru **ou** `{value, evidence, confidence}` → (valor, evidência, conf)."""
    if isinstance(raw, dict):
        return raw.get("value"), raw.get("evidence", []), _clamp_conf(raw.get("confidence"))
    return raw, [], None


def _claim_str(raw: Any, index: dict[str, RawDocument]) -> Claim[str] | None:
    """`Claim[str]` a partir do campo (valor cru ou embrulhado); `None` se vazio."""
    value, ev, conf = _unwrap(raw)
    if value is None or not str(value).strip():
        return None
    return Claim[str](value=str(value).strip(), evidence=_evidence(ev, index), confidence=conf)


def _claim_int(raw: Any, index: dict[str, RawDocument]) -> Claim[int] | None:
    """`Claim[int]` (ex.: ano de fundação); `None` se ausente/não-inteiro."""
    value, ev, conf = _unwrap(raw)
    try:
        ivalue = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return Claim[int](value=ivalue, evidence=_evidence(ev, index), confidence=conf)


def _items(data: dict, key: str) -> Iterable[dict]:
    """Itera a coleção `key` do JSON, ignorando entradas não-objeto."""
    return (i for i in data.get(key, []) if isinstance(i, dict))


def _str(item: dict, key: str) -> str | None:
    """Campo de texto não-vazio de um item, ou `None`."""
    v = item.get(key)
    return str(v).strip() if v is not None and str(v).strip() else None


def _products(data: dict, index: dict[str, RawDocument]) -> list[Product]:
    out: list[Product] = []
    for it in _items(data, "produtos"):
        nome = _str(it, "nome")
        if not nome:
            continue
        out.append(
            Product(
                nome=nome,
                descricao=_str(it, "descricao"),
                categoria=_str(it, "categoria"),
                evidence=_evidence(it.get("evidence", []), index),
            )
        )
    return out


def _customers(data: dict, index: dict[str, RawDocument]) -> list[Customer]:
    out: list[Customer] = []
    for it in _items(data, "clientes"):
        nome = _str(it, "nome")
        if not nome:
            continue
        ent = it.get("enterprise")
        out.append(
            Customer(
                nome=nome,
                segmento=_str(it, "segmento"),
                enterprise=bool(ent) if isinstance(ent, bool) else None,
                evidence=_evidence(it.get("evidence", []), index),
            )
        )
    return out


def _technologies(data: dict, index: dict[str, RawDocument]) -> list[Technology]:
    out: list[Technology] = []
    for it in _items(data, "tecnologias"):
        nome = _str(it, "nome")
        if not nome:
            continue
        out.append(
            Technology(
                nome=nome,
                categoria=_str(it, "categoria"),
                uso=_str(it, "uso"),
                evidence=_evidence(it.get("evidence", []), index),
            )
        )
    return out


def _founders(data: dict, index: dict[str, RawDocument]) -> list[Founder]:
    """Founders — só info profissional pública (§2/LGPD); a guarda final é da persistência."""
    out: list[Founder] = []
    for it in _items(data, "founders"):
        nome = _str(it, "nome")
        if not nome:
            continue
        out.append(
            Founder(
                nome=nome,
                cargo=_str(it, "cargo"),
                linkedin_url=_maybe_url(it.get("linkedin_url")),
                background=_str(it, "background"),
                evidence=_evidence(it.get("evidence", []), index),
            )
        )
    return out


def _funding(data: dict, index: dict[str, RawDocument]) -> Funding | None:
    raw = data.get("funding")
    if not isinstance(raw, dict):
        return None
    try:
        total = float(raw["total_raised_usd"]) if raw.get("total_raised_usd") is not None else None
    except (TypeError, ValueError):
        total = None
    investors = [str(i).strip() for i in raw.get("investors", []) if str(i).strip()]
    f = Funding(
        total_raised_usd=total if (total is None or total >= 0) else None,
        last_round_stage=_str(raw, "last_round_stage"),
        last_round_date=_str(raw, "last_round_date"),
        investors=investors,
        evidence=_evidence(raw.get("evidence", []), index),
    )
    # Só vira funding se trouxe algum sinal (evita um bloco vazio sem evidência).
    if any(
        (f.total_raised_usd, f.last_round_stage, f.last_round_date, f.investors, f.evidence)
    ):
        return f
    return None


def parse_profile(
    text: str,
    *,
    query: str,
    docs: Sequence[RawDocument],
    run_id: str | None = None,
) -> StartupProfile:
    """Converte o JSON do Super (prompt extractor@v1) num `StartupProfile` (puro/offline).

    Tolerante por design (como o `_parse_plan` do search_planner): campos escalares aceitam
    valor cru **ou** `{value, evidence, confidence}`; campos desconhecidos são ignorados (o
    schema é `extra="forbid"`, mas montamos campo a campo); itens malformados são pulados sem
    derrubar. `nome` cai na `query` se o modelo não devolver. `source_urls` é a proveniência
    **agregada** das fontes realmente coletadas (não o que o modelo alegar).
    """
    data = _loads_json_object(text)
    index = _doc_index(docs)

    nome = _str(data, "nome") or query.strip() or "(desconhecida)"
    source_urls = list(dict.fromkeys(str(d.url) for d in docs))

    return StartupProfile(
        nome=nome,
        website=_maybe_url(data.get("website")),
        pais=_str(data, "pais") or "BR",
        cnpj=_claim_str(data.get("cnpj"), index),
        descricao=_claim_str(data.get("descricao"), index),
        setor=_claim_str(data.get("setor"), index),
        ano_fundacao=_claim_int(data.get("ano_fundacao"), index),
        produtos=_products(data, index),
        clientes=_customers(data, index),
        founders=_founders(data, index),
        tecnologias=_technologies(data, index),
        funding=_funding(data, index),
        run_id=run_id,
        source_urls=source_urls,  # type: ignore[arg-type]
    )


# ------------------------------------------------------------------ extração (núcleo testável)


def extract_profile(
    query: str,
    docs: Sequence[RawDocument],
    *,
    extract: ExtractFn,
    run_id: str | None = None,
) -> StartupProfile | None:
    """Roda o adapter de extração e tipa a saída; **degrada p/ `None`** em qualquer falha.

    Núcleo testável do nó: o adapter (`extract`) é injetado (fake nos testes, Nemotron-Super
    em produção) e devolve o JSON cru; aqui só se faz parse + tipagem com proveniência. Erro
    de rede/JSON/validação vira `None` (não alucina) — o caller registra e segue (F2.7 julga).
    A causa exata (timeout do Super, JSON inválido, validação) é **logada** (`logger.warning`)
    p/ o run não falhar mudo: uma empresa forte com perfil `None` é quase sempre LLM/parse, não
    ausência de dado — sem o log, o porquê some no `except` largo (diag de runs como rivio.ai).
    """
    try:
        raw = extract(query, docs)
        return parse_profile(raw, query=query, docs=docs, run_id=run_id)
    except Exception as exc:  # noqa: BLE001 — LLM/parse/validação falhou → degrada sem derrubar
        logger.warning(
            "extractor: extração falhou para %r (%s: %s)", query, type(exc).__name__, exc
        )
        return None


def _user_payload(
    query: str, docs: Sequence[RawDocument], *, doc_chars: int, max_docs: int = DEFAULT_MAX_DOCS
) -> str:
    """Turno do usuário p/ o extractor@v1: nome-alvo + documentos (url + conteúdo aparado).

    Capa **nº de docs** (`max_docs`, ordem de prioridade preservada) e **chars/doc** (`doc_chars`)
    p/ o payload não estourar o teto de 120s do Super (F7.6) — ver caps no topo do módulo.
    """
    documents = [
        {"url": str(d.url), "content": d.content[:doc_chars]} for d in docs if d.content.strip()
    ][:max_docs]
    return json.dumps({"company_name": query, "documents": documents}, ensure_ascii=False)


def _default_extract(
    query: str, docs: Sequence[RawDocument], *, run_id: str | None = None
) -> str:
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

    prompt = get_prompt("extractor")
    config = traced_config(node="extractor", prompt_version=prompt.version_tag, run_id=run_id)
    # Reasoning é do prompt (F0.12), mas gateável por settings: desligar deixa a extração em
    # segundos (sem CoT longa) quando o NIM está lento — manda o directive **explícito** "off" p/
    # o Super não cair no default. Default ON preserva a qualidade do caminho real (eval F7).
    reasoning = prompt.reasoning and get_settings().extractor_reasoning
    messages: list = [reasoning_system_message(reasoning)]
    messages.append(SystemMessage(content=prompt.template))
    messages.append(HumanMessage(content=_user_payload(query, docs, doc_chars=DEFAULT_DOC_CHARS)))
    return cached_completion(prompt, messages, config=config)  # cache F2.14


# ------------------------------------------------------------------------------- nó


def extractor(
    state: GraphState,
    *,
    extract: ExtractFn | None = None,
    persist: Callable[[StartupProfile], None] | None = None,
) -> dict:
    """F2.5 — estrutura os `raw_docs` num `StartupProfile`; devolve update parcial do estado.

    Offline por default (M2/DoD): sem `raw_docs` (espinha sem rede) **ou** com o LLM
    desligado e sem `extract` injetado, é um no-op limpo (`{}`) — `profile` fica `None`. Liga
    a extração real injetando `extract` (testes/worker) ou com `settings.extractor_use_llm`
    (produção via grafo). A persistência (F1.10) é o hook opcional `persist` (desligado por
    padrão — o backbone não toca o banco). Falhas **acumulam** em `state.errors` sem derrubar
    o run; a não-extração deixa `profile=None` p/ o evidence_validator (F2.7) decidir.
    """
    docs = state.raw_docs
    if not docs:
        return {}  # nada coletado (offline default) → sem profile, espinha verde (M2)
    if extract is None and not get_settings().extractor_use_llm:
        return {}  # LLM desligado e sem adapter injetado → no-op

    adapter: ExtractFn = extract or (lambda q, d: _default_extract(q, d, run_id=state.run_id))
    profile = extract_profile(state.query, docs, extract=adapter, run_id=state.run_id)
    if profile is None:
        # Desambigua a falha p/ o trace/briefing (F5.7/F2.12): sem nenhum doc com texto é coleta
        # vazia (página JS/anti-bot — problema de scraper); com texto e ainda assim sem perfil é
        # falha do modelo/parse (timeout do Super, JSON inválido — ver `logger.warning` acima).
        com_conteudo = sum(1 for d in docs if d.content.strip())
        causa = (
            "conteúdo coletado mas o modelo/parse não estruturou um perfil "
            "(timeout/JSON — ver log do worker)"
            if com_conteudo
            else "nenhum documento com texto aproveitável (provável página JS/anti-bot)"
        )
        note = (
            f"extractor: extração não produziu um perfil utilizável — "
            f"{len(docs)} doc(s) coletado(s), {com_conteudo} com conteúdo; {causa}"
        )
        return {"errors": [*state.errors, note]}

    update: dict = {"profile": profile}
    if persist is not None:
        try:
            persist(profile)
        except Exception as exc:  # noqa: BLE001 — persistência falhou → erro rastreável; perfil fica
            update["errors"] = [
                *state.errors,
                f"extractor: persistência falhou ({type(exc).__name__}: {exc})",
            ]
    return update


__all__ = [
    "ExtractFn",
    "parse_profile",
    "extract_profile",
    "extractor",
]
