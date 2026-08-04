"""Testes do adapter de extração de artigo trafilatura (F1.4).

O núcleo (`extract`/`_parse`) é validado **offline** sobre HTML/dicts fixos — o
trafilatura é puro-Python e já está instalado, então a extração real roda sem
rede. O `fetch` (download) só é exercido de fato no smoke gated por rede, espelhando
o smoke real da busca (F1.1), Firecrawl (F1.2) e Playwright (F1.3).
"""

from __future__ import annotations

import os

import pytest

from packages.scraping import Article
from packages.scraping import extract_article as extract
from packages.scraping import fetch_article as fetch
from packages.scraping.article import _parse

# Artigo de notícia típico: o sinal está no <article>; nav/related/rodapé são ruído.
_HTML = """
<html>
  <head>
    <title>Startup paulista de IA levanta seed</title>
    <meta name="author" content="Maria Silva">
    <meta property="article:published_time" content="2026-05-01">
    <meta name="description" content="Rodada para acelerar produto de agentes.">
  </head>
  <body>
    <nav>Home Mercado Tecnologia</nav>
    <article>
      <h1>Startup paulista de IA levanta seed</h1>
      <p>A startup anunciou uma rodada seed para escalar sua plataforma de agentes.</p>
      <p>O produto usa RAG e embeddings para responder com base em documentos do cliente.</p>
    </article>
    <aside>Leia também: outras 10 startups para ficar de olho</aside>
    <footer>Copyright veiculo</footer>
  </body>
</html>
"""

# Dict no shape do `bare_extraction(as_dict=True)` — base do teste de mapeamento.
_DOC = {
    "url": "https://news.example/post-final",
    "title": "Startup paulista de IA levanta seed",
    "author": "Maria Silva",
    "date": "2026-05-01",
    "description": "Rodada para acelerar produto de agentes.",
    "sitename": "Veículo",
    "hostname": "news.example",
    "language": "pt",
    "categories": ["Startups"],
    "tags": ["IA", "funding"],
    "text": "A startup anunciou uma rodada seed.",
    "raw_text": "A startup anunciou uma rodada seed.",
    "comments": "",
}


def test_parse_maps_editorial_fields() -> None:
    article = _parse("https://news.example/pedido-original", _DOC)
    assert isinstance(article, Article)
    assert article.url == "https://news.example/post-final"  # url do doc tem prioridade
    assert article.text == "A startup anunciou uma rodada seed."
    assert article.title == "Startup paulista de IA levanta seed"
    assert article.author == "Maria Silva"
    assert article.date == "2026-05-01"
    assert article.description == "Rodada para acelerar produto de agentes."
    assert article.sitename == "Veículo"
    assert article.language == "pt"
    assert article.categories == ("Startups",)
    assert article.tags == ("IA", "funding")
    assert not article.is_empty


def test_parse_metadata_excludes_lxml_and_duplicates() -> None:
    article = _parse("https://x.example", _DOC)
    # campos de primeira classe e duplicatas/cruas não poluem o metadata
    for dropped in ("text", "raw_text", "title", "url", "comments", "body", "commentsbody"):
        assert dropped not in article.metadata
    # o resto útil (hostname) fica disponível, sem chaves vazias
    assert article.metadata["hostname"] == "news.example"
    assert all(v not in (None, "", [], ()) for v in article.metadata.values())


def test_parse_none_doc_is_empty() -> None:
    article = _parse("https://x.example/none", None)
    assert article.url == "https://x.example/none"  # cai na url pedida
    assert article.text == ""
    assert article.is_empty
    assert article.metadata == {}
    assert article.categories == ()


def test_extract_isolates_main_article_offline() -> None:
    article = extract(_HTML, url="https://news.example/post")
    assert isinstance(article, Article)
    assert "rodada seed" in article.text
    assert "RAG e embeddings" in article.text
    # boilerplate de nav/related/rodapé fica de fora do corpo do artigo
    assert "Leia também" not in article.text
    assert "Copyright veiculo" not in article.text
    assert "Home Mercado" not in article.text
    # metadados editoriais (proveniência F1.9 / datar sinal F2)
    assert article.title == "Startup paulista de IA levanta seed"
    assert article.author == "Maria Silva"
    assert article.date == "2026-05-01"
    assert not article.is_empty


def test_extract_blank_html_is_empty() -> None:
    article = extract("   ", url="https://x.example")
    assert article.is_empty
    assert article.url == "https://x.example"


def test_extract_textless_html_is_empty() -> None:
    # HTML sem nenhum texto extraível → Article vazio, não erro (roteador F1.7 segue adiante)
    article = extract("<html><body><div></div></body></html>", url="https://x.example")
    assert article.is_empty


def test_fetch_rejects_empty_url() -> None:
    with pytest.raises(ValueError):
        fetch("   ")


@pytest.mark.skipif(
    not os.environ.get("TAPI_NETWORK_TESTS"),
    reason="fetch real (F1.4) faz download; opt-in via TAPI_NETWORK_TESTS=1 (não roda no CI)",
)
def test_fetch_real() -> None:
    """Smoke real (rede): baixa e extrai uma página estática simples.

    Único caminho não coberto offline é o download (`fetch_url`); a extração em si
    já é exercida real sobre HTML fixo nos testes acima. Gated por env var porque,
    diferente dos outros adapters, o trafilatura não tem chave/browser que o CI
    naturalmente não tenha.
    """
    article = fetch("https://example.com")
    assert article.url.startswith("http")
