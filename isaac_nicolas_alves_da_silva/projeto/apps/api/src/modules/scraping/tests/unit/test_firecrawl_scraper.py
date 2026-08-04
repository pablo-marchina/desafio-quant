"""Testes do FirecrawlScraper."""

import httpx
import pytest

from apps.api.src.modules.scraping.application.dto import ScrapingInput
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.domain.exceptions import (
    ContentExtractionError,
    ScrapingRequestError,
)
from apps.api.src.modules.scraping.infrastructure.scrapers.firecrawl_scraper import (
    FirecrawlScraper,
)


def _make_scraper(handler) -> FirecrawlScraper:
    return FirecrawlScraper(
        api_key="test-key",
        base_url="https://api.firecrawl.dev",
        client_factory=lambda: httpx.AsyncClient(
            base_url="https://api.firecrawl.dev",
            transport=httpx.MockTransport(handler),
        ),
    )


def _ok_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "success": True,
            "data": {
                "markdown": "# Acme Startup\n\nSomos uma empresa de IA.",
                "html": "<h1>Acme Startup</h1><p>Somos uma empresa de IA.</p>",
                "metadata": {
                    "title": "Acme Startup",
                    "sourceURL": "https://acme.com.br",
                    "statusCode": 200,
                    "language": "pt",
                    "ogTitle": "Acme - AI company",
                },
            },
        },
        request=request,
    )


@pytest.mark.anyio
async def test_firecrawl_scraper_returns_markdown_as_raw_text() -> None:
    scraper = _make_scraper(_ok_response)
    output = await scraper.scrape(ScrapingInput(url="https://acme.com.br"))

    assert output.method == ScrapingMethod.FIRECRAWL
    assert "Acme Startup" in output.raw_text
    assert output.raw_text.startswith("# Acme Startup")


@pytest.mark.anyio
async def test_firecrawl_scraper_populates_title_and_final_url() -> None:
    scraper = _make_scraper(_ok_response)
    output = await scraper.scrape(ScrapingInput(url="https://acme.com.br"))

    assert output.title == "Acme Startup"
    assert output.final_url == "https://acme.com.br"
    assert output.status_code == 200


@pytest.mark.anyio
async def test_firecrawl_scraper_includes_metadata_engine() -> None:
    scraper = _make_scraper(_ok_response)
    output = await scraper.scrape(ScrapingInput(url="https://acme.com.br"))

    assert output.metadata["extraction_engine"] == "firecrawl"


@pytest.mark.anyio
async def test_firecrawl_scraper_raises_on_empty_markdown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"success": True, "data": {"markdown": "", "html": "", "metadata": {}}},
            request=request,
        )

    scraper = _make_scraper(handler)
    with pytest.raises(ContentExtractionError):
        await scraper.scrape(ScrapingInput(url="https://acme.com.br"))


@pytest.mark.anyio
async def test_firecrawl_scraper_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": "quota exceeded"}, request=request)

    scraper = _make_scraper(handler)
    with pytest.raises(ScrapingRequestError, match="402"):
        await scraper.scrape(ScrapingInput(url="https://acme.com.br"))


def test_firecrawl_scraper_requires_non_empty_api_key() -> None:
    with pytest.raises(ValueError):
        FirecrawlScraper(api_key="")
