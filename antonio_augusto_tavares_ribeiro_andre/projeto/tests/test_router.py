"""Testes do roteador de fetch estático vs dinâmico (F1.7).

Tudo roda **offline**: o núcleo de decisão (`is_insufficient`) e a re-extração do html
renderizado (`extract_rendered`, que usa trafilatura/bs4 — puros) não tocam a rede; a
orquestração (`route`/`fetch`) é exercitada injetando adapters falsos no lugar do
Firecrawl (F1.2) e do Playwright (F1.3), provando a lógica de fallback estático→dinâmico
sem chave nem navegador.
"""

from __future__ import annotations

import pytest

from packages.scraping import FetchResult, extract_rendered, is_insufficient, route
from packages.scraping.dynamic import RenderedPage
from packages.scraping.firecrawl import ExtractedPage

# html de notícia com <article> — o trafilatura isola o corpo de forma confiável offline.
_ARTICLE_HTML = """
<html><head><title>Startup de IA levanta seed</title></head><body>
  <nav>Home Mercado</nav>
  <article>
    <h1>Startup de IA levanta seed</h1>
    <p>A startup anunciou uma rodada seed para escalar sua plataforma de agentes.</p>
    <p>O produto usa RAG e embeddings para responder com base nos documentos do cliente.</p>
  </article>
  <footer>Copyright veiculo</footer>
</body></html>
"""

# página estruturada (carreiras): valor em links/meta, não em prosa — caso do bs4.
_STRUCTURED_HTML = """
<html lang="pt"><head><title>Vagas</title>
  <meta name="description" content="Trabalhe com agentes e RAG."></head>
  <body><a href="/vagas/mle">MLE</a><a href="https://x.example/sobre">Sobre</a></body>
</html>
"""


def test_is_insufficient_threshold() -> None:
    assert is_insufficient("", min_chars=10)
    assert is_insufficient("   curto   ", min_chars=10)  # conta texto strip-ado
    assert not is_insufficient("x" * 10, min_chars=10)
    assert not is_insufficient("conteúdo bem longo e suficiente", min_chars=10)


def test_extract_rendered_article_uses_trafilatura() -> None:
    rendered = RenderedPage(
        url="https://news.example/post", html=_ARTICLE_HTML, text="texto basico", status_code=200
    )
    result = extract_rendered("article", rendered)
    assert result.rendered is True
    assert result.strategy == "playwright+trafilatura"
    assert "rodada seed" in result.text
    assert "Copyright veiculo" not in result.text  # boilerplate fora (trafilatura)
    assert result.html == _ARTICLE_HTML  # DOM preservado p/ re-extração/proveniência
    assert result.status_code == 200


def test_extract_rendered_structured_uses_soup() -> None:
    rendered = RenderedPage(
        url="https://x.example/vagas", html=_STRUCTURED_HTML, text="", status_code=200
    )
    result = extract_rendered("structured", rendered)
    assert result.strategy == "playwright+soup"
    assert result.metadata["description"] == "Trabalhe com agentes e RAG."
    assert result.rendered is True


def test_extract_rendered_falls_back_to_render_text_when_no_article() -> None:
    # html sem artigo extraível → cai no texto visível básico do render (F1.3), não erro
    rendered = RenderedPage(
        url="https://x.example",
        html="<html><body><div></div></body></html>",
        text="conteudo visivel do render",
        status_code=200,
    )
    result = extract_rendered("clean", rendered)
    assert result.strategy == "playwright"
    assert result.text == "conteudo visivel do render"


def test_route_returns_static_when_sufficient() -> None:
    # Firecrawl traz conteúdo suficiente → não renderiza (render nem é chamado).
    called = {"render": False}

    def fake_scrape(url: str) -> ExtractedPage:
        return ExtractedPage(url=url, markdown="conteúdo principal limpo e suficiente " * 10)

    def fake_render(url: str) -> RenderedPage:
        called["render"] = True
        return RenderedPage(url=url, html="", text="")

    result = route("https://x.example", scrape=fake_scrape, render=fake_render)
    assert isinstance(result, FetchResult)
    assert result.strategy == "firecrawl"
    assert result.rendered is False
    assert called["render"] is False  # estático bastou → sem custo de render


def test_route_falls_back_to_render_when_static_thin() -> None:
    # Firecrawl volta casca rasa (página JS) → cai para o Playwright e re-extrai.
    def fake_scrape(url: str) -> ExtractedPage:
        return ExtractedPage(url=url, markdown="oi")  # < min_chars

    def fake_render(url: str) -> RenderedPage:
        return RenderedPage(url=url, html=_ARTICLE_HTML, text="basico", status_code=200)

    result = route("https://x.example", intent="clean", scrape=fake_scrape, render=fake_render)
    assert result.rendered is True
    assert result.strategy == "playwright+trafilatura"
    assert "rodada seed" in result.text


def test_route_force_render_skips_static() -> None:
    called = {"scrape": False}

    def fake_scrape(url: str) -> ExtractedPage:
        called["scrape"] = True
        return ExtractedPage(url=url, markdown="x" * 500)

    def fake_render(url: str) -> RenderedPage:
        return RenderedPage(url=url, html=_ARTICLE_HTML, text="basico", status_code=200)

    result = route("https://x.example", force_render=True, scrape=fake_scrape, render=fake_render)
    assert called["scrape"] is False  # pulou o estático
    assert result.rendered is True


def test_route_keeps_static_when_render_empty() -> None:
    # estático raso mas não-vazio + render que falha → devolve o estático (melhor esforço).
    def fake_scrape(url: str) -> ExtractedPage:
        return ExtractedPage(url=url, markdown="algum texto curto")

    def fake_render(url: str) -> RenderedPage:
        return RenderedPage(url=url, html="", text="")  # render vazio

    result = route("https://x.example", scrape=fake_scrape, render=fake_render)
    assert result.strategy == "firecrawl"
    assert result.text == "algum texto curto"


def test_route_falls_back_to_render_when_static_raises() -> None:
    # Firecrawl FALHA DURO (ex.: sem crédito → PaymentRequired) → em vez de abortar a coleta, cai pro
    # render (Playwright, grátis) e re-extrai. Regressão do rivio.ai (2026-06-23): site `clean` com
    # Firecrawl esgotado rendia 0 docs → perfil vazio → classe/AIMI falsos.
    def boom_scrape(url: str) -> ExtractedPage:
        raise RuntimeError("Payment Required: Insufficient credits to perform this request")

    def fake_render(url: str) -> RenderedPage:
        return RenderedPage(url=url, html=_ARTICLE_HTML, text="basico", status_code=200)

    result = route("https://x.example", intent="clean", scrape=boom_scrape, render=fake_render)
    assert result.rendered is True
    assert result.strategy == "playwright+trafilatura"
    assert "rodada seed" in result.text


def test_route_reraises_static_error_when_render_also_empty() -> None:
    # Estático falha E o render não rende nada → propaga o erro original (rastreável no scraper),
    # não devolve vazio silencioso que mascararia a causa (ex.: Firecrawl sem crédito).
    def boom_scrape(url: str) -> ExtractedPage:
        raise RuntimeError("Payment Required")

    def empty_render(url: str) -> RenderedPage:
        return RenderedPage(url=url, html="", text="")

    with pytest.raises(RuntimeError, match="Payment Required"):
        route("https://x.example", intent="clean", scrape=boom_scrape, render=empty_render)


def test_route_rejects_empty_url() -> None:
    with pytest.raises(ValueError):
        route("   ")
