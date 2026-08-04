"""Testes da funcao pura _extract_internal_links (P0d).

Verifica que links internos relevantes sao extraidos corretamente do HTML
e que links irrelevantes (externos, media, auth) sao filtrados.
"""

from apps.api.src.modules.orchestration.application.use_cases.advance_url_ingestion_job import (
    _extract_internal_links,
)

BASE_URL = "https://acme.example.com"


def test_extracts_product_and_about_links() -> None:
    html = (
        '<a href="/plataforma">Nossa Plataforma</a>'
        '<a href="/sobre">Sobre nós</a>'
    )
    links = _extract_internal_links(html, BASE_URL)
    urls = set(links)
    assert f"{BASE_URL}/plataforma" in urls
    assert f"{BASE_URL}/sobre" in urls


def test_filters_out_external_links() -> None:
    html = '<a href="https://other.example.com/page">Externo</a>'
    links = _extract_internal_links(html, BASE_URL)
    assert not any("other.example.com" in u for u in links)


def test_filters_out_auth_paths() -> None:
    html = (
        '<a href="/login">Login</a>'
        '<a href="/signup">Signup</a>'
        '<a href="/dashboard">Dashboard</a>'
    )
    links = _extract_internal_links(html, BASE_URL)
    assert links == []


def test_filters_out_media_files() -> None:
    html = (
        '<a href="/logo.png">Logo</a>'
        '<a href="/style.css">CSS</a>'
        '<a href="/app.js">JS</a>'
    )
    links = _extract_internal_links(html, BASE_URL)
    assert links == []


def test_filters_root_and_fragments() -> None:
    html = (
        '<a href="/">Home</a>'
        '<a href="#section">Ancora</a>'
        '<a href="javascript:void(0)">JS</a>'
        '<a href="mailto:hi@acme.com">Email</a>'
    )
    links = _extract_internal_links(html, BASE_URL)
    assert links == []


def test_relevant_paths_score_higher_and_come_first() -> None:
    html = (
        '<a href="/random-path">Random</a>'
        '<a href="/blog">Blog</a>'
        '<a href="/sobre">Sobre</a>'
    )
    links = _extract_internal_links(html, BASE_URL)
    # paths com keyword (blog, sobre) devem vir antes de random-path
    keyword_links = [u for u in links if "blog" in u or "sobre" in u]
    random_links = [u for u in links if "random" in u]
    assert keyword_links, "Esperava links com keyword"
    if random_links:
        # todos keyword links devem vir antes do random
        last_keyword_pos = max(links.index(u) for u in keyword_links)
        first_random_pos = min(links.index(u) for u in random_links)
        assert last_keyword_pos < first_random_pos


def test_deduplicates_same_url() -> None:
    html = (
        '<a href="/sobre">Sobre</a>'
        '<a href="/sobre">Sobre novamente</a>'
    )
    links = _extract_internal_links(html, BASE_URL)
    assert links.count(f"{BASE_URL}/sobre") == 1


def test_resolves_relative_urls() -> None:
    html = '<a href="produtos/plataforma">Produto</a>'
    links = _extract_internal_links(html, f"{BASE_URL}/home/")
    assert any("produtos" in u for u in links)


def test_empty_html_returns_empty_list() -> None:
    assert _extract_internal_links("", BASE_URL) == []


def test_html_without_links_returns_empty_list() -> None:
    assert _extract_internal_links("<p>Texto sem links.</p>", BASE_URL) == []
