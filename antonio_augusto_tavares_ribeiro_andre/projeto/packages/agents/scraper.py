"""Nó **scraper** (F2.4): map paralelo sobre as fontes priorizadas → `raw_docs`.

Segundo nó do grafo (ARQUITETURA §3). Consome o plano do search_planner (F2.3) — a
lista achatada `state.sources` (URLs §9 + termos de busca) — e devolve os documentos
brutos (`RawDocument`, F0.5) que o extractor (F2.5) vai estruturar. É o ponto onde os
adapters de coleta da F1 entram no grafo, sob o maestro de roteamento (F1.7):

- **URL** (http/https): vai direto ao roteador `route` (F1.7), que escolhe estático
  (Firecrawl/trafilatura/bs4) vs dinâmico (Playwright) e re-extrai conforme o intent.
- **termo de busca**: resolve candidatas via Tavily (`search`, F1.1) e coleta as
  primeiras liberadas — é como o single-company (cujas fontes são quase todas termos:
  "Acme site oficial", "Acme LinkedIn", …) vira conteúdo real.

Cada URL passa pela **política de ToS travada (F1.15)** antes do fetch (`source_policy`):
fonte `api_only`/`deny` (§9.1 proprietária) é **pulada** e registrada em `errors`, nunca
coletada direto; o **intent** do roteador é inferido do tipo da fonte §9 (notícia→article,
diretório/programa→structured, demais→clean), como o próprio roteador documenta ("o caller
decide o intent a partir da fonte §9"). A proveniência mínima (F1.9) viaja no `RawDocument`:
`url` + `fetched_at` + `content_hash` (texto normalizado, base da dedup) + `source_type` (a
cadeia de adapters que produziu o texto). A evidência citável completa (tabela `evidence`,
`source_policy`) é gravada no caminho de persistência do extractor (F2.5).

**Decisão de design (política headless b/d):** o "MAP paralelo" do §3 é feito **dentro
do nó** (pool de threads sobre as fontes — coleta é I/O-bound), e **não** como um
fan-out LangGraph (`Send`) com reducer `operator.add` no canal `raw_docs`. Por quê: (1)
mantém o scraper como **um** nó na espinha linear travada na F2.1 — o backbone que o
retry condicional `evidence_validator→scraper` (F2.7) e os terminais (F2.12/F2.13) vão
ancorar; um fan-out via `Send` complicaria esse loop de retry e o fan-in; (2) não
antecipa decisão de schema do estado — `raw_docs` segue com a semântica de sobrescrita
da F2.1 (o nó devolve a lista inteira de uma vez, o que também é o certo no re-scrape do
retry: substitui em vez de duplicar). O caminho `Send`+reducer fica documentado como
alternativa plugável. Os resultados são reordenados pela ordem das fontes, então o
`raw_docs` é **determinista** independente da ordem de término das threads (ethos F2.14).

Como no search_planner (F2.3), o caminho **offline é o default**: sem rede o nó é um
no-op limpo (`{}` — mantém a espinha verde, M2/DoD "grafo end-to-end"). A coleta real é
**plugável** atrás de `settings.scraper_use_network` (default off) **ou** de adapters
injetados (`fetch=`/`search=`), que é como os testes exercitam o map/gate/dedup sem rede
e o worker (F2.10) liga a coleta de verdade. Quota/robots/rate-limit por fetch continuam
sendo responsabilidade dos adapters (F1.8); aqui é orquestração + política de fonte.

Hooks de tasks futuras: regra de N fontes + retry (F2.7) lê este `raw_docs`; guarda de
custo por run (F2.11) e cache de inferência (F2.14) ficam fora do scraping (frescor).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from packages.config import get_settings
from packages.schemas import GraphState, RawDocument
from packages.scraping.provenance import content_hash
from packages.scraping.seeds import load_sources
from packages.scraping.source_policy import verdict as tos_verdict

if TYPE_CHECKING:
    from packages.scraping.router import ContentKind, FetchResult
    from packages.scraping.search import SearchResult

# Adapters de rede injetáveis (default = os reais da F1, importados preguiçosamente).
FetchFn = Callable[[str, "ContentKind"], "FetchResult"]
SearchFn = Callable[[str], "Sequence[SearchResult]"]

# Concorrência do map e quantas candidatas coletar por termo de busca (free tier F1.8).
DEFAULT_MAX_WORKERS = 8
DEFAULT_RESULTS_PER_QUERY = 2

# Tipo da fonte §9 → intent do roteador (F1.7). Fonte não-listada (site oficial/empresa)
# cai no default "clean" (Firecrawl → conteúdo principal limpo, bom p/ o RAG/extração).
_TYPE_INTENT: dict[str, ContentKind] = {
    "news": "article",
    "directory": "structured",
    "program": "structured",
}


@dataclass(frozen=True)
class _Target:
    """Uma URL liberada pela política de ToS (F1.15), já com o intent do roteador."""

    url: str
    intent: ContentKind


def _is_url(source: str) -> bool:
    """True se a fonte é uma URL concreta (coleta direta) vs. um termo de busca."""
    return source.strip().lower().startswith(("http://", "https://"))


#: Query que JÁ é um domínio nu (single-company por domínio, ex.: "rivio.ai"): ≥1 ponto, sem
#: espaço/esquema. Habilita o fetch direto do site oficial (ver `_query_site_url`).
_BARE_DOMAIN_RE = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+$", re.IGNORECASE)


def _query_site_url(query: str) -> str | None:
    """`https://<domínio>` quando a query é um domínio (rivio.ai); senão `None`.

    Sem isto, uma query single-company por domínio entra no search_planner só como **termo de
    busca** — o site oficial pode nunca ser coletado e a coleta cai em diretórios genéricos →
    perfil vazio → classe/AIMI falsos (bug real: `rivio.ai` virou non-AI/0 porque o site dele
    nunca foi fetchado, 2026-06-22). Nome com espaço ("Hand Talk") e query de descoberta não casam.
    """
    q = query.strip()
    if not q or " " in q:
        return None
    if _is_url(q):
        return q
    return f"https://{q}" if _BARE_DOMAIN_RE.match(q) else None


def _intent_for(source_type: str | None) -> ContentKind:
    """Intent do roteador (F1.7) a partir do tipo da fonte §9; default `clean`."""
    return _TYPE_INTENT.get(source_type or "", "clean")


def _source_type(source_id: str | None) -> str | None:
    """Tipo §9 (`news`/`directory`/`program`) da fonte governante, se listada (F0.9)."""
    if not source_id:
        return None
    for src in load_sources():
        if src.id == source_id:
            return src.type
    return None


def _gate(urls: Iterable[str], errors: list[str]) -> list[_Target]:
    """Aplica a política de ToS (F1.15) e anexa o intent; barra `api_only`/`deny`.

    URL de fonte proprietária (§9.1) é **pulada** (registrada em `errors`), nunca
    coletada direto — usa-se API/parceria. Site oficial/notícia (allow/não-listada)
    passa. Ordem preservada; cada URL avaliada uma única vez (verdict carrega a fonte).
    """
    targets: list[_Target] = []
    for url in urls:
        v = tos_verdict(url)
        if not v.allowed:
            errors.append(
                f"{url}: ToS '{v.policy}' barra coleta direta — usar API/parceria (F1.15)"
            )
            continue
        targets.append(_Target(url=url, intent=_intent_for(_source_type(v.source_id))))
    return targets


def _resolve_targets(
    source: str, searcher: SearchFn, results_per_query: int, errors: list[str]
) -> list[_Target]:
    """Fonte → URLs coletáveis: URL direta, ou termo → Tavily (F1.1) → top-K liberadas."""
    s = source.strip()
    if _is_url(s):
        return _gate([s], errors)
    try:
        candidates = [r.url for r in searcher(s)]
    except Exception as exc:  # noqa: BLE001 — busca falhou (quota/rede/chave) → registra e segue
        errors.append(f"{s}: busca Tavily falhou ({type(exc).__name__}: {exc})")
        return []
    return _gate(candidates, errors)[:results_per_query]


def _fetch_one(target: _Target, fetcher: FetchFn) -> tuple[RawDocument | None, str | None]:
    """Coleta uma URL liberada (F1.7) → `RawDocument` com proveniência (F1.9), ou erro.

    Nunca levanta: falha de rede/compliance vira string de erro; página sem texto útil
    não vira documento (não é erro fatal — o validador de evidência decide, F2.7).
    """
    try:
        result = fetcher(target.url, target.intent)
    except Exception as exc:  # noqa: BLE001 — adapter/compliance falhou → erro rastreável
        return None, f"{target.url}: fetch falhou ({type(exc).__name__}: {exc})"
    if result.is_empty:
        return None, f"{target.url}: sem conteúdo útil (vazio)"
    try:
        doc = RawDocument(
            url=result.url or target.url,
            content=result.text,
            fetched_at=datetime.now(UTC),
            content_hash=content_hash(result.text),
            source_type=result.strategy or None,
        )
    except Exception as exc:  # noqa: BLE001 — URL inválida p/ HttpUrl etc. → descarta com nota
        return None, f"{target.url}: documento inválido ({type(exc).__name__}: {exc})"
    return doc, None


def _collect_source(
    source: str, fetcher: FetchFn, searcher: SearchFn, results_per_query: int
) -> tuple[list[RawDocument], list[str]]:
    """Processa **uma** fonte (unidade do map): resolve URLs e coleta cada uma."""
    errors: list[str] = []
    docs: list[RawDocument] = []
    for target in _resolve_targets(source, searcher, results_per_query, errors):
        doc, err = _fetch_one(target, fetcher)
        if doc is not None:
            docs.append(doc)
        if err is not None:
            errors.append(err)
    return docs, errors


def _default_fetch(url: str, intent: ContentKind) -> FetchResult:
    """Adapter real de coleta: o roteador estático↔dinâmico da F1.7 (import preguiçoso).

    `scraper_force_render` (F0.3) pula o Firecrawl e usa só o render local (Playwright +
    trafilatura) no intent `clean` — o jeito de rodar **sem crédito de Firecrawl** (o render
    já é grátis/local e era o fallback; a flag o torna primário). Não afeta `article`/`structured`,
    que já não usam Firecrawl.
    """
    from packages.scraping.router import fetch as route

    # Só o intent `clean` usa Firecrawl; `article`/`structured` já são trafilatura/bs4 (grátis),
    # então não há o que pular neles — forçar render lá só adicionaria custo de Playwright.
    force_render = get_settings().scraper_force_render and intent == "clean"
    return route(url, intent=intent, force_render=force_render)


def _default_search(query: str) -> Sequence[SearchResult]:
    """Adapter real de busca: Tavily (F1.1, import preguiçoso). Requer `TAVILY_API_KEY`."""
    from packages.scraping.search import search

    return search(query)


def scrape_sources(
    sources: Sequence[str],
    *,
    fetch: FetchFn,
    search: SearchFn,
    max_workers: int = DEFAULT_MAX_WORKERS,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
) -> tuple[list[RawDocument], list[str]]:
    """MAP paralelo sobre `sources` → (`raw_docs` deduplicados, `errors`).

    Núcleo testável do nó: as fontes são coletadas concorrentemente (pool de threads,
    I/O-bound), mas o resultado é **reordenado pela ordem das fontes** e deduplicado por
    `(url, content_hash)` — determinístico apesar do paralelismo (ethos F2.14). Os
    adapters de rede são parâmetros (injete os fakes nos testes; os reais em produção).
    """
    clean = [s for s in sources if s and s.strip()]
    if not clean:
        return [], []

    indexed: dict[int, tuple[list[RawDocument], list[str]]] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(clean)))) as pool:
        futures = {
            pool.submit(_collect_source, src, fetch, search, results_per_query): i
            for i, src in enumerate(clean)
        }
        for fut in as_completed(futures):
            indexed[futures[fut]] = fut.result()

    raw_docs: list[RawDocument] = []
    errors: list[str] = []
    seen: set[tuple[str, str | None]] = set()
    for i in range(len(clean)):  # ordem das fontes → reprodutível
        docs, errs = indexed[i]
        for doc in docs:
            key = (str(doc.url), doc.content_hash)
            if key not in seen:
                seen.add(key)
                raw_docs.append(doc)
        errors.extend(errs)
    return raw_docs, errors


def scraper(
    state: GraphState,
    *,
    fetch: FetchFn | None = None,
    search: SearchFn | None = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
) -> dict:
    """F2.4 — coleta paralela das fontes priorizadas; devolve update parcial do estado.

    Offline por default (M2/DoD): sem adapters injetados e com
    `settings.scraper_use_network` desligado, é um no-op limpo (`{}`) — a espinha roda
    ponta a ponta sem rede. Liga a coleta real injetando `fetch`/`search` (testes/worker)
    ou com a flag de rede (caminho de produção via grafo). Erros de coleta são
    **acumulados** em `state.errors` (rastreável), sem derrubar o run.
    """
    sources = [s for s in state.sources if s and s.strip()]
    # Garante o site da própria empresa quando a query é um domínio (rivio.ai): o search_planner
    # pode listá-lo só como termo de busca, e sem o fetch direto a coleta cai em diretórios
    # genéricos → perfil vazio. Prepende como fonte direta (ToS/F1.15 e o dedup do scrape governam).
    site = _query_site_url(state.query)
    if site is not None and site not in sources:
        sources = [site, *sources]
    if not sources:
        return {}
    if fetch is None and not get_settings().scraper_use_network:
        return {}  # default offline: sem rede, sem erros — mantém a espinha verde (M2)

    raw_docs, errors = scrape_sources(
        sources,
        fetch=fetch or _default_fetch,
        search=search or _default_search,
        max_workers=max_workers,
        results_per_query=results_per_query,
    )
    update: dict = {"raw_docs": raw_docs}
    if errors:
        update["errors"] = [*state.errors, *errors]
    return update


__all__ = [
    "FetchFn",
    "SearchFn",
    "scrape_sources",
    "scraper",
]
