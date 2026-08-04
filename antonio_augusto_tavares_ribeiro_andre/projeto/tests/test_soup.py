"""Testes do adapter de parsing estruturado BeautifulSoup (F1.5).

O núcleo (`extract`/`extract_links`/`select_text`) é validado **offline** sobre HTML
fixo — o bs4 é puro-Python e já está instalado, então o parsing real roda sem rede.
O `fetch` (GET) só é exercido de fato no smoke gated por rede, espelhando o smoke
real da busca (F1.1), Firecrawl (F1.2), Playwright (F1.3) e trafilatura (F1.4).
"""

from __future__ import annotations

import os

import pytest

from packages.scraping import Link, ParsedPage, extract_links, select_text
from packages.scraping import fetch_html as fetch
from packages.scraping import parse_html as parse

# Página de carreiras típica: o valor está na estrutura (vagas, links a seguir,
# meta) e não num artigo em prosa — o caso de uso do bs4 vs trafilatura (F1.4).
_HTML = """
<html lang="pt">
  <head>
    <title>Vagas — Startup de IA</title>
    <meta name="description" content="Trabalhe com agentes e RAG.">
    <meta property="og:site_name" content="Startup de IA">
    <style>.x { color: red; }</style>
    <script>var ignore = 'lixo de script';</script>
  </head>
  <body>
    <nav><a href="/">Home</a> <a href="/sobre">Sobre</a></nav>
    <main>
      <h1>Vagas abertas</h1>
      <ul class="jobs">
        <li>Machine Learning Engineer</li>
        <li>LLM/Agents Engineer</li>
      </ul>
      <p>Stack: Python, RAG, embeddings.</p>
      <a href="https://linkedin.com/company/startup-ia">LinkedIn</a>
      <a href="mailto:rh@startup.example">Email</a>
      <a href="/vagas/mle">Detalhe MLE</a>
      <a href="/vagas/mle">Detalhe MLE (dup)</a>
    </main>
  </body>
</html>
"""

_BASE = "https://startup.example/vagas"


def test_extract_parses_title_text_and_metadata() -> None:
    page = parse(_HTML, url=_BASE)
    assert isinstance(page, ParsedPage)
    assert page.title == "Vagas — Startup de IA"
    # texto visível: conteúdo de script/style fica de fora
    assert "Vagas abertas" in page.text
    assert "Machine Learning Engineer" in page.text
    assert "lixo de script" not in page.text
    assert "color: red" not in page.text
    # metadados (name, Open Graph, lang) p/ enriquecimento de perfil (F2)
    assert page.metadata["description"] == "Trabalhe com agentes e RAG."
    assert page.metadata["og:site_name"] == "Startup de IA"
    assert page.metadata["lang"] == "pt"
    assert not page.is_empty


def test_extract_absolutizes_dedups_and_filters_links() -> None:
    page = parse(_HTML, url=_BASE)
    urls = [link.url for link in page.links]
    # relativos absolutizados contra a base
    assert "https://startup.example/" in urls
    assert "https://startup.example/sobre" in urls
    # externo http mantido; mailto descartado (não é página a seguir)
    assert "https://linkedin.com/company/startup-ia" in urls
    assert not any(u.startswith("mailto:") for u in urls)
    # link repetido aparece uma vez só (dedup), preservando o texto da 1ª âncora
    assert urls.count("https://startup.example/vagas/mle") == 1
    mle = next(link for link in page.links if link.url.endswith("/vagas/mle"))
    assert isinstance(mle, Link)
    assert mle.text == "Detalhe MLE"


def test_extract_links_same_domain_filter() -> None:
    # o crawler (F1.6) usa same_domain p/ não sair do site da startup
    internal = extract_links(_HTML, base_url=_BASE, same_domain=True)
    hosts = {u.url.split("/")[2] for u in internal}
    assert hosts == {"startup.example"}
    assert all("linkedin.com" not in u.url for u in internal)


def test_extract_links_uses_base_href_tag() -> None:
    html = (
        "<html><head><base href='https://cdn.example/app/'></head>"
        "<body><a href='page.html'>x</a></body></html>"
    )
    links = extract_links(html)
    assert links == (Link(url="https://cdn.example/app/page.html", text="x"),)


def test_select_text_targets_signal_elements() -> None:
    # extração dirigida p/ a taxonomia de sinais AI-native (F1.11)
    jobs = select_text(_HTML, "ul.jobs li")
    assert jobs == ["Machine Learning Engineer", "LLM/Agents Engineer"]
    assert select_text(_HTML, ".inexistente") == []


def test_extract_blank_html_is_empty() -> None:
    page = parse("   ", url="https://x.example")
    assert page.is_empty
    assert page.url == "https://x.example"
    assert page.links == ()
    assert page.metadata == {}


def test_extract_links_only_is_not_empty() -> None:
    # sem texto, mas com links a seguir → ainda útil p/ o crawler (F1.6)
    html = '<html><body><a href="/x"><img src="i.png"></a></body></html>'
    page = parse(html, url="https://x.example")
    assert page.text == ""
    assert page.links
    assert not page.is_empty


def test_fetch_rejects_empty_and_non_http_url() -> None:
    with pytest.raises(ValueError):
        fetch("   ")
    with pytest.raises(ValueError):
        fetch("file:///etc/passwd")


@pytest.mark.skipif(
    not os.environ.get("TAPI_NETWORK_TESTS"),
    reason="fetch real (F1.5) faz GET; opt-in via TAPI_NETWORK_TESTS=1 (não roda no CI)",
)
def test_fetch_real() -> None:
    """Smoke real (rede): único caminho não coberto offline é o GET (`urlopen`)."""
    page = fetch("https://example.com")
    assert page.url.startswith("http")
    assert page.title
