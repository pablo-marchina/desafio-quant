"""Testes do crawler de varredura em escala Scrapy (F1.6).

O núcleo é validado **offline**: `collectable_seeds` (gate de ToS F1.15) e
`parse_response` (parsing + decisão de quais links seguir) não dependem do Scrapy nem
de rede. A integração real com o Scrapy é exercitada **sem reactor** alimentando um
`HtmlResponse` fixo ao `parse` do spider — prova que o spider visita a página, anexa
ao sink e só segue links do mesmo domínio. A varredura completa (`crawl`, que sobe o
reactor do Twisted) só roda no smoke gated por rede, como nos adapters reais (F1.1–F1.5).
"""

from __future__ import annotations

import importlib.util
import os

import pytest

from packages.scraping import CrawledPage, CrawlPlan, collectable_seeds
from packages.scraping.crawler import (
    DEFAULT_USER_AGENT,
    _build_spider,
    _host_allowed,
    parse_response,
)
from packages.scraping.seeds import Source

_HAS_SCRAPY = importlib.util.find_spec("scrapy") is not None


def _source(id_: str, url: str, policy: str) -> Source:
    """Source mínima para os testes de política (campos não usados ficam neutros)."""
    return Source(
        id=id_,
        name=id_,
        url=url,
        type="program",
        country="BR",
        policy=policy,  # type: ignore[arg-type]
        robots="allow",
        tos_scraping="permitted",
        legal_basis="teste",
    )


# Página de listagem típica (portfólio de aceleradora): links internos a paginar +
# links externos de startups — estes viram a fila de candidatas do cohort builder (F1.14).
_HTML = """
<html lang="pt">
  <head><title>Portfólio</title></head>
  <body>
    <h1>Startups aceleradas</h1>
    <ul>
      <li><a href="/portfolio/empresa-a">Empresa A</a></li>
      <li><a href="https://empresa-a.com.br">site A</a></li>
      <li><a href="https://empresa-b.com">site B</a></li>
    </ul>
    <a href="/portfolio?page=2">Próxima página</a>
    <a href="mailto:contato@aceleradora.com.br">contato</a>
  </body>
</html>
"""
_BASE = "https://aceleradora.com.br/portfolio"
_ALLOWED = ("aceleradora.com.br",)


def test_collectable_seeds_gates_by_tos_policy() -> None:
    # F1.15: só fontes `allow` viram seed; api_only/deny vão para `skipped`.
    sources = [
        _source("news-ok", "https://braziljournal.com", "allow"),
        _source("distrito", "https://distrito.me", "api_only"),
        _source("startse", "https://www.startse.com", "deny"),
    ]
    plan = collectable_seeds(sources)
    assert isinstance(plan, CrawlPlan)
    assert plan.start_urls == ("https://braziljournal.com",)
    assert plan.allowed_domains == ("braziljournal.com",)
    assert set(plan.skipped) == {"distrito", "startse"}


def test_collectable_seeds_dedups_domains_in_order() -> None:
    sources = [
        _source("a", "https://x.com/portfolio", "allow"),
        _source("b", "https://x.com/cohort", "allow"),
        _source("c", "https://y.com", "allow"),
    ]
    plan = collectable_seeds(sources)
    assert plan.allowed_domains == ("x.com", "y.com")  # dedup preservando ordem


def test_host_allowed_matches_host_and_subdomain() -> None:
    assert _host_allowed("x.com", ("x.com",))
    assert _host_allowed("blog.x.com", ("x.com",))  # subdomínio
    assert not _host_allowed("x.com.evil.com", ("x.com",))  # não é sufixo de label
    assert not _host_allowed("other.com", ("x.com",))
    assert not _host_allowed("x.com", ())  # sem escopo → não segue nada


def test_parse_response_keeps_all_links_but_follows_same_domain() -> None:
    page, follow = parse_response(
        url=_BASE, html=_HTML, allowed_hosts=_ALLOWED, status_code=200, depth=1
    )
    assert isinstance(page, CrawledPage)
    assert page.depth == 1
    assert page.status_code == 200
    assert "Startups aceleradas" in page.text
    # links da página guardam TUDO (inclusive externos) p/ a fila do F1.14
    urls = {link.url for link in page.links}
    assert "https://empresa-a.com.br" in urls
    assert "https://empresa-b.com" in urls
    assert not any(u.startswith("mailto:") for u in urls)  # bs4 já filtra mailto (F1.5)
    # mas a varredura só SEGUE o mesmo domínio (confinamento F1.8)
    assert "https://aceleradora.com.br/portfolio/empresa-a" in follow
    assert "https://aceleradora.com.br/portfolio?page=2" in follow
    assert "https://empresa-a.com.br" not in follow
    assert "https://empresa-b.com" not in follow


def test_parse_response_empty_html() -> None:
    page, follow = parse_response(url="https://x.example", html="   ", allowed_hosts=("x.example",))
    assert page.is_empty
    assert follow == ()


@pytest.mark.skipif(not _HAS_SCRAPY, reason="integração F1.6 precisa do scrapy instalado")
def test_spider_parses_response_and_follows_same_domain_offline() -> None:
    """Exercita o spider real do Scrapy sem reactor: alimenta um HtmlResponse fixo.

    Prova que `parse` anexa a página ao sink e só emite `Request` para o mesmo
    domínio (offsite/externo não vira requisição de varredura).
    """
    from scrapy import Request
    from scrapy.http import HtmlResponse

    sink: list[CrawledPage] = []
    spider_cls = _build_spider(
        start_urls=[_BASE],
        allowed_domains=_ALLOWED,
        source_by_host={"aceleradora.com.br": "aceleradora"},
        sink=sink,
        max_pages=50,
        max_depth=2,
        download_delay=0.0,
        user_agent=DEFAULT_USER_AGENT,
    )
    spider = spider_cls()
    request = Request(_BASE, meta={"depth": 0})
    response = HtmlResponse(
        url=_BASE, body=_HTML.encode("utf-8"), encoding="utf-8", request=request, status=200
    )

    requests = list(spider.parse(response))

    # página visitada foi para o sink, com proveniência da fonte (F1.9)
    assert len(sink) == 1
    assert sink[0].source_id == "aceleradora"
    assert sink[0].depth == 0
    # só seguiu links internos; cada um carrega depth+1 p/ o limite de profundidade
    followed = {r.url for r in requests}
    assert "https://aceleradora.com.br/portfolio/empresa-a" in followed
    assert all("empresa-a.com.br" not in u and "empresa-b.com" not in u for u in followed)
    assert all(r.meta["depth"] == 1 for r in requests)


@pytest.mark.skipif(not _HAS_SCRAPY, reason="integração F1.6 precisa do scrapy instalado")
def test_spider_stops_following_at_max_depth_offline() -> None:
    from scrapy import Request
    from scrapy.http import HtmlResponse

    sink: list[CrawledPage] = []
    spider_cls = _build_spider(
        start_urls=[_BASE],
        allowed_domains=_ALLOWED,
        source_by_host={},
        sink=sink,
        max_pages=50,
        max_depth=1,
        download_delay=0.0,
        user_agent=DEFAULT_USER_AGENT,
    )
    spider = spider_cls()
    request = Request(_BASE, meta={"depth": 1})  # já no limite
    response = HtmlResponse(
        url=_BASE, body=_HTML.encode("utf-8"), encoding="utf-8", request=request, status=200
    )
    requests = list(spider.parse(response))
    assert len(sink) == 1  # ainda coleta a página atual
    assert requests == []  # mas não segue além de max_depth


def test_crawl_raises_without_collectable_source() -> None:
    from packages.scraping import crawl

    with pytest.raises(ValueError, match="nenhuma fonte coletável"):
        crawl([_source("distrito", "https://distrito.me", "api_only")])


@pytest.mark.skipif(
    not os.environ.get("TAPI_NETWORK_TESTS"),
    reason="crawl real (F1.6) sobe o reactor e faz GET; opt-in via TAPI_NETWORK_TESTS=1",
)
def test_crawl_real() -> None:
    """Smoke real (rede + reactor): varre 1 página de uma fonte allow."""
    from packages.scraping import crawl

    pages = crawl([_source("example", "https://example.com", "allow")], max_pages=1, max_depth=0)
    assert pages
    assert pages[0].url.startswith("http")
