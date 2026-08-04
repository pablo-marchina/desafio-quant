"""Testes do nó scraper (F2.4).

Tudo offline/determinista (a coleta real é opt-in via `scraper_use_network` + adapters
F1). Exercita o núcleo `scrape_sources` com adapters de rede **injetados** (fakes):
- map sobre fontes: URL direta vs termo de busca (Tavily → top-K);
- gate de ToS (F1.15): fonte `api_only`/`deny` é pulada e registrada em `errors`;
- intent do roteador (F1.7) inferido do tipo da fonte §9 (news→article, program→structured);
- dedup por (url, content_hash) e ordem determinista (= ordem das fontes), apesar das threads;
- erros de fetch/busca acumulados sem derrubar o run;
- o nó: no-op limpo offline (default) e update parcial coerente com fetch injetado.
"""

from __future__ import annotations

import packages.agents.scraper as sc
from packages.agents.scraper import scrape_sources, scraper
from packages.schemas import GraphState
from packages.scraping.router import ContentKind, FetchResult
from packages.scraping.search import SearchResult


def _page(url: str, text: str = "Acme constrói agentes de IA para fintechs.") -> FetchResult:
    """`FetchResult` (F1.7) de teste — texto suficiente p/ virar `RawDocument`."""
    return FetchResult(url=url, text=text, strategy="firecrawl")


def _fetch_ok(url: str, intent: ContentKind) -> FetchResult:
    return _page(url, text=f"conteúdo de {url}")


def _no_search(query: str) -> list[SearchResult]:
    raise AssertionError("busca não deveria ser chamada para URLs diretas")


# ----------------------------------------------------------------- map + coleta direta


def test_scrape_sources_collects_allowed_urls_in_order() -> None:
    docs, errors = scrape_sources(
        ["https://acme.ai", "https://braziljournal.com/acme"],
        fetch=_fetch_ok,
        search=_no_search,
    )
    assert errors == []
    assert [str(d.url) for d in docs] == ["https://acme.ai/", "https://braziljournal.com/acme"]
    # proveniência mínima (F1.9): hash do conteúdo + a estratégia que produziu o texto.
    assert all(d.content_hash and d.source_type == "firecrawl" for d in docs)


def test_intent_inferred_from_source_type() -> None:
    seen: dict[str, ContentKind] = {}

    def capture(url: str, intent: ContentKind) -> FetchResult:
        seen[url] = intent
        return _page(url)

    scrape_sources(
        [
            "https://acme.ai",  # não-listada → clean (default)
            "https://braziljournal.com/x",  # news §9.2 → article
            "https://www.nvidia.com/en-us/startups/",  # program → structured
        ],
        fetch=capture,
        search=_no_search,
    )
    assert seen["https://acme.ai"] == "clean"
    assert seen["https://braziljournal.com/x"] == "article"
    assert seen["https://www.nvidia.com/en-us/startups/"] == "structured"


# ---------------------------------------------------------------------- gate de ToS (F1.15)


def test_tos_blocked_source_is_skipped_and_recorded() -> None:
    docs, errors = scrape_sources(
        ["https://www.startse.com/empresa/acme", "https://acme.ai"],  # deny, allow
        fetch=_fetch_ok,
        search=_no_search,
    )
    assert [str(d.url) for d in docs] == ["https://acme.ai/"]  # só a liberada coletou
    assert any("startse" in e and "ToS" in e for e in errors)


def test_api_only_directory_also_blocked() -> None:
    docs, errors = scrape_sources(
        ["https://distrito.me/startup/acme"], fetch=_fetch_ok, search=_no_search
    )
    assert docs == []
    assert any("distrito" in e for e in errors)


# ------------------------------------------------------------------- termo de busca (Tavily)


def test_search_term_resolved_to_top_k_allowed_urls() -> None:
    def fake_search(query: str) -> list[SearchResult]:
        return [
            SearchResult(url=f"https://r{i}.com", title="", snippet="", score=0.9) for i in range(3)
        ]

    docs, errors = scrape_sources(
        ["fintechs AI em SP"], fetch=_fetch_ok, search=fake_search, results_per_query=2
    )
    assert errors == []
    assert [str(d.url) for d in docs] == ["https://r0.com/", "https://r1.com/"]  # top-2


def test_search_failure_recorded_not_fatal() -> None:
    def boom(query: str) -> list[SearchResult]:
        raise RuntimeError("quota Tavily estourou")

    docs, errors = scrape_sources(["fintechs AI"], fetch=_fetch_ok, search=boom)
    assert docs == []
    assert any("busca Tavily falhou" in e for e in errors)


# --------------------------------------------------------------------- dedup + robustez


def test_dedup_by_url_and_content_hash() -> None:
    docs, _ = scrape_sources(
        ["https://acme.ai", "https://acme.ai"], fetch=_fetch_ok, search=_no_search
    )
    assert len(docs) == 1  # mesma url + mesmo conteúdo → uma evidência só


def test_empty_fetch_is_not_a_document() -> None:
    docs, errors = scrape_sources(
        ["https://acme.ai"], fetch=lambda u, i: _page(u, text="   "), search=_no_search
    )
    assert docs == []
    assert any("sem conteúdo útil" in e for e in errors)


def test_fetch_error_recorded_not_fatal() -> None:
    def boom(url: str, intent: ContentKind) -> FetchResult:
        raise RuntimeError("playwright travou")

    docs, errors = scrape_sources(["https://acme.ai"], fetch=boom, search=_no_search)
    assert docs == []
    assert any("fetch falhou" in e for e in errors)


# ------------------------------------------------------------------------------- nó


def test_node_offline_is_noop(monkeypatch) -> None:
    # sem fetch injetado e sem a flag de rede → no-op limpo (espinha verde, M2).
    monkeypatch.setattr(sc, "get_settings", lambda: _FakeSettings(use_network=False))
    state = GraphState(run_id="r1", query="Acme", sources=["https://acme.ai"])
    assert scraper(state) == {}


def test_node_no_sources_returns_empty() -> None:
    state = GraphState(run_id="r1", query="Acme")
    assert scraper(state, fetch=_fetch_ok) == {}


def test_node_with_injected_fetch_returns_docs() -> None:
    state = GraphState(run_id="r1", query="Acme", sources=["https://acme.ai"])
    update = scraper(state, fetch=_fetch_ok, search=_no_search)
    assert [str(d.url) for d in update["raw_docs"]] == ["https://acme.ai/"]
    assert "errors" not in update  # sem erros → não polui o estado


def test_node_accumulates_errors_onto_state() -> None:
    state = GraphState(
        run_id="r1",
        query="Acme",
        sources=["https://www.startse.com/x", "https://acme.ai"],
        errors=["erro anterior"],
    )
    update = scraper(state, fetch=_fetch_ok, search=_no_search)
    assert [str(d.url) for d in update["raw_docs"]] == ["https://acme.ai/"]
    assert update["errors"][0] == "erro anterior"  # preserva os antigos
    assert any("startse" in e for e in update["errors"][1:])  # + os novos


# ------------------------------------------------- query-domínio → fetch direto do site (F2.4)


def test_query_site_url_recognizes_bare_domain() -> None:
    assert sc._query_site_url("rivio.ai") == "https://rivio.ai"
    assert sc._query_site_url("https://rivio.ai/about") == "https://rivio.ai/about"  # já é URL
    assert sc._query_site_url("Hand Talk") is None  # nome com espaço
    assert sc._query_site_url("rivio") is None  # sem ponto/TLD
    assert sc._query_site_url("fintechs de fraude") is None  # query de descoberta


def test_node_fetches_query_domain_even_when_planner_omits_it() -> None:
    # Bug real (rivio.ai → non-AI/0, 2026-06-22): o search_planner listou o domínio só como termo,
    # o site oficial nunca foi coletado → perfil vazio → classe/AIMI falsos. Uma query-domínio agora
    # vira fetch DIRETO do site, mesmo que o planner não o liste como URL.
    fetched: list[str] = []

    def capture(url: str, intent: ContentKind) -> FetchResult:
        fetched.append(url)
        return _page(url)

    state = GraphState(
        run_id="r1", query="rivio.ai", sources=["rivio site oficial", "https://braziljournal.com"]
    )
    update = scraper(state, fetch=capture, search=lambda q: [])
    assert "https://rivio.ai" in fetched  # o site da própria empresa entrou na coleta
    assert any(str(d.url).startswith("https://rivio.ai") for d in update["raw_docs"])


class _FakeSettings:
    def __init__(self, *, use_network: bool) -> None:
        self.scraper_use_network = use_network
