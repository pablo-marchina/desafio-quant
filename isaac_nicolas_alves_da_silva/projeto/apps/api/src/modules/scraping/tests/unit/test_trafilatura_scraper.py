"""Testes da estrategia especializada em extrair conteudo principal."""

import pytest

from apps.api.src.modules.scraping.application.dto import ScrapingInput, ScrapingOutput
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.domain.exceptions import ContentExtractionError
from apps.api.src.modules.scraping.infrastructure.scrapers.trafilatura_scraper import (
    TrafilaturaScraper,
)


class SourceScraperStub:
    """Simula o downloader seguro que fornece HTML para a Trafilatura."""

    method = ScrapingMethod.BEAUTIFULSOUP

    async def scrape(self, scraping_input: ScrapingInput) -> ScrapingOutput:
        return ScrapingOutput(
            source_url=scraping_input.url,
            final_url=scraping_input.url,
            title="Noticia",
            raw_html="<nav>Menu</nav><article>Conteudo principal</article>",
            raw_text="Menu Conteudo principal",
            status_code=200,
            content_type="text/html",
            method=self.method,
            metadata={"response_bytes": 55},
        )


class ArticleSourceScraperStub(SourceScraperStub):
    """Fornece um artigo com navegacao para exercitar a biblioteca real."""

    async def scrape(self, scraping_input: ScrapingInput) -> ScrapingOutput:
        article = (
            "A plataforma utiliza inteligencia artificial para analisar "
            "documentos empresariais, automatizar processos e apoiar equipes. "
        ) * 12
        return ScrapingOutput(
            source_url=scraping_input.url,
            final_url=scraping_input.url,
            title="Artigo sobre inteligencia artificial",
            raw_html=(
                "<html><body><nav>Inicio Produtos Contato</nav>"
                f"<article><h1>Pesquisa</h1><p>{article}</p></article>"
                "<footer>Politica de privacidade</footer></body></html>"
            ),
            raw_text=f"Inicio Produtos Contato {article} Politica de privacidade",
            status_code=200,
            content_type="text/html",
            method=self.method,
        )


@pytest.mark.anyio
async def test_real_trafilatura_extracts_article_content() -> None:
    """Integracao local prova que a biblioteca real consegue limpar um artigo."""

    output = await TrafilaturaScraper(
        source_scraper=ArticleSourceScraperStub(),
    ).scrape(ScrapingInput(url="https://example.com/article"))

    assert "plataforma utiliza inteligencia artificial" in output.raw_text
    assert "Politica de privacidade" not in output.raw_text
    assert output.method is ScrapingMethod.TRAFILATURA


@pytest.mark.anyio
async def test_extracts_main_content_and_preserves_source_metadata() -> None:
    """A estrategia deve trocar o texto e preservar os dados da coleta."""

    received_options = {}

    def extractor(raw_html: str, **options) -> str:
        received_options.update(options)
        return "Conteudo principal"

    output = await TrafilaturaScraper(
        source_scraper=SourceScraperStub(),
        extractor=extractor,
    ).scrape(ScrapingInput(url="https://example.com/article"))

    assert output.raw_text == "Conteudo principal"
    assert output.method is ScrapingMethod.TRAFILATURA
    assert output.metadata["response_bytes"] == 55
    assert output.metadata["extraction_engine"] == "trafilatura"
    assert output.metadata["main_content_extracted"] is True
    assert received_options["favor_precision"] is True
    assert received_options["include_comments"] is False


@pytest.mark.anyio
async def test_empty_extraction_allows_pipeline_fallback() -> None:
    """Falha de extracao deve permitir que outra estrategia seja tentada."""

    scraper = TrafilaturaScraper(
        source_scraper=SourceScraperStub(),
        extractor=lambda raw_html, **options: None,
    )

    with pytest.raises(ContentExtractionError, match="nao encontrou"):
        await scraper.scrape(ScrapingInput(url="https://example.com/article"))
