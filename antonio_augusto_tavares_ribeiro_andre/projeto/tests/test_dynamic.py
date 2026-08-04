"""Testes do adapter de renderização dinâmica Playwright (F1.3).

A extração de texto (`extract_text`/`_parse`) é validada offline sobre HTML fixo —
não precisa de navegador nem rede. A renderização real (`render`) só roda com o
`playwright` instalado **e** o Chromium baixado; usa um `file://` local com JS que
injeta conteúdo, provando que o adapter executa JavaScript (o objetivo do F1.3) sem
depender da internet. Espelha o smoke offline/real da busca (F1.1) e Firecrawl (F1.2).
"""

from __future__ import annotations

import importlib.util

import pytest

from packages.scraping import RenderedPage, render
from packages.scraping.dynamic import _parse, extract_text

_HAS_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None

# HTML típico de SPA: o texto útil está espalhado, com script/style que devem sair.
_HTML = """
<html>
  <head>
    <title>Startup de IA</title>
    <style>.x { color: red; }</style>
    <script>var ignore = 'lixo de script';</script>
  </head>
  <body>
    <nav>Home Sobre</nav>
    <main>
      <h1>Plataforma de Agentes</h1>
      <p>Construímos agentes com <b>RAG</b> &amp; embeddings.</p>
      <p>Rodada seed em 2026.</p>
    </main>
    <noscript>ative o JavaScript</noscript>
  </body>
</html>
"""


def test_extract_text_drops_script_and_style() -> None:
    text = extract_text(_HTML)
    assert "lixo de script" not in text
    assert "color: red" not in text
    assert "ative o JavaScript" not in text  # <noscript> também sai
    assert "Plataforma de Agentes" in text


def test_extract_text_decodes_entities_and_keeps_inline() -> None:
    text = extract_text(_HTML)
    # entidade decodificada e texto inline (<b>) preservado na mesma linha
    assert "agentes com RAG & embeddings." in text


def test_extract_text_separates_blocks() -> None:
    text = extract_text(_HTML)
    # os dois <p> viram parágrafos distintos (fronteira de bloco), não linha colada
    assert "embeddings.\n\nRodada seed em 2026." in text
    assert "\n\n\n" not in text  # quebras redundantes colapsadas


def test_extract_text_empty() -> None:
    assert extract_text("") == ""
    assert extract_text("<html><body></body></html>") == ""


def test_parse_maps_fields_and_computes_text() -> None:
    page = _parse(
        "https://startup.example/app",
        _HTML,
        title="Startup de IA",
        status_code=200,
        metadata={"lang": "pt"},
    )
    assert isinstance(page, RenderedPage)
    assert page.url == "https://startup.example/app"
    assert page.html == _HTML  # DOM cru preservado p/ extração fina (F1.4/F1.5)
    assert "Plataforma de Agentes" in page.text
    assert page.title == "Startup de IA"
    assert page.status_code == 200
    assert page.metadata["lang"] == "pt"
    assert not page.is_empty


def test_parse_is_empty_for_blank_dom() -> None:
    page = _parse("https://x.example", "<html><body></body></html>")
    assert page.text == ""
    assert page.is_empty
    assert page.metadata == {}


def test_render_rejects_empty_url() -> None:
    with pytest.raises(ValueError):
        render("   ")


@pytest.mark.skipif(
    not _HAS_PLAYWRIGHT, reason="render real (F1.3) precisa do playwright instalado"
)
def test_render_executes_javascript(tmp_path: object) -> None:
    """Prova o diferencial do F1.3: o conteúdo só existe após o JS rodar."""
    from playwright.sync_api import Error as PlaywrightError

    html = (
        "<html><head><title>Dinamica</title></head><body>"
        "<div id='app'></div>"
        "<script>document.getElementById('app').textContent = 'Conteudo via JS';</script>"
        "</body></html>"
    )
    page_file = tmp_path / "spa.html"  # type: ignore[operator]
    page_file.write_text(html, encoding="utf-8")

    try:
        result = render(page_file.as_uri(), wait_until="load")
    except PlaywrightError as exc:  # navegador não baixado (playwright install)
        pytest.skip(f"Chromium do Playwright indisponível: {exc}")

    assert result.title == "Dinamica"
    assert "Conteudo via JS" in result.text  # o JS executou e o texto apareceu
    assert "id='app'" not in result.text  # markup fora, só texto visível
    assert not result.is_empty
