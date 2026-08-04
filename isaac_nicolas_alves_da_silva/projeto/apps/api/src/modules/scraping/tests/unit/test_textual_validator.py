"""Testes do validador textual especializado."""

from apps.api.src.modules.scraping.application.dto import ScrapingOutput
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.infrastructure.validators.textual_validator import (
    TextualValidator,
)


def make_output(raw_html: str, raw_text: str) -> ScrapingOutput:
    return ScrapingOutput(
        source_url="https://example.com",
        final_url="https://example.com",
        title="Pagina",
        raw_html=raw_html,
        raw_text=raw_text,
        status_code=200,
        content_type="text/html",
        method=ScrapingMethod.BEAUTIFULSOUP,
    )


def make_extracted_output(raw_html: str, raw_text: str) -> ScrapingOutput:
    """Representa texto principal extraido, preservando o HTML para auditoria."""

    output = make_output(raw_html, raw_text)
    return ScrapingOutput(
        source_url=output.source_url,
        final_url=output.final_url,
        title=output.title,
        raw_html=output.raw_html,
        raw_text=output.raw_text,
        status_code=output.status_code,
        content_type=output.content_type,
        method=ScrapingMethod.TRAFILATURA,
        metadata={"main_content_extracted": True},
    )


def test_detects_page_dominated_by_boilerplate() -> None:
    """Menu e rodape dominantes devem gerar problema recuperavel."""

    navigation = " ".join(f"Menu item {index}" for index in range(120))
    article = "Produto de inteligencia artificial para empresas. " * 10
    html = f"<html><nav>{navigation}</nav><main>{article}</main></html>"

    result = TextualValidator().validate(
        make_output(html, f"{navigation} {article}")
    )

    assert "high_boilerplate" in result.problems
    assert result.score < 0.8


def test_does_not_penalize_original_html_after_main_content_extraction() -> None:
    """HTML original nao deve invalidar texto ja limpo pela Trafilatura."""

    navigation = " ".join(f"Menu item {index}" for index in range(120))
    article = (
        "A plataforma de inteligencia artificial analisa documentos e "
        "automatiza processos empresariais com resultados auditaveis. "
    ) * 14
    html = f"<html><nav>{navigation}</nav><article>{article}</article></html>"

    result = TextualValidator().validate(make_extracted_output(html, article))

    assert "high_boilerplate" not in result.problems
    assert result.score >= 0.80


def test_measures_high_link_ratio_as_warning() -> None:
    """Pagina composta principalmente por links deve ser sinalizada."""

    links = " ".join(
        f"<a href='/{index}'>Startup artificial intelligence {index}</a>"
        for index in range(100)
    )

    result = TextualValidator().validate(
        make_output(f"<html><main>{links}</main></html>", beautiful_text(links))
    )

    assert "high_link_ratio" in result.warnings


def test_good_article_has_high_text_score_without_structure_warnings() -> None:
    """Artigo com paragrafo principal deve manter score alto."""

    article = (
        "A plataforma utiliza inteligencia artificial e machine learning "
        "para analisar operacoes industriais e apoiar decisoes empresariais. "
    ) * 18
    html = f"<html><main><article><p>{article}</p></article></main></html>"

    result = TextualValidator().validate(make_output(html, article))

    assert result.score >= 0.80
    assert "high_boilerplate" not in result.problems
    assert "high_link_ratio" not in result.warnings
    assert "language_pt" in result.warnings


def test_detects_probable_english_language() -> None:
    """Palavras funcionais devem identificar texto provavelmente em ingles."""

    article = (
        "The platform is designed for companies and helps teams analyze "
        "documents with artificial intelligence in the cloud. "
    ) * 12

    result = TextualValidator().validate(
        make_output(f"<html><main>{article}</main></html>", article)
    )

    assert "language_en" in result.warnings


def test_short_text_has_unknown_language() -> None:
    """Texto curto nao deve receber classificacao de idioma confiante."""

    result = TextualValidator().validate(
        make_output("<html><p>AI platform</p></html>", "AI platform")
    )

    assert "language_unknown" in result.warnings


def beautiful_text(html_fragment: str) -> str:
    """Extrai texto simples da fixture sem depender do scraper real."""

    from bs4 import BeautifulSoup

    return BeautifulSoup(html_fragment, "html.parser").get_text(" ", strip=True)
