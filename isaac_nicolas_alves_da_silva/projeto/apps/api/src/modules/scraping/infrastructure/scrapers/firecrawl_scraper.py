"""Fallback de scraping usando a API paga do Firecrawl.

Firecrawl e a 4a estrategia, acionada so quando BS4 + Trafilatura + Playwright
esgotam — por isso e' o fallback mais caro e mais capaz (headless completo,
anti-bot, extrai Markdown estruturado).

A factory so inclui esta estrategia quando `FIRECRAWL_API_KEY` esta configurada.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from apps.api.src.modules.scraping.application.dto import ScrapingInput, ScrapingOutput
from apps.api.src.modules.scraping.application.ports import Scraper
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.domain.exceptions import (
    ContentExtractionError,
    ScrapingRequestError,
)

_FIRECRAWL_SCRAPE_ENDPOINT = "/v1/scrape"
_TIMEOUT_SECONDS = 60.0


class FirecrawlScraper(Scraper):
    """Coleta pagina via API Firecrawl e retorna o Markdown extraido."""

    method = ScrapingMethod.FIRECRAWL

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.firecrawl.dev",
        *,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("FIRECRAWL_API_KEY nao pode ser vazio.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client_factory = client_factory or self._default_client

    def _default_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=_TIMEOUT_SECONDS,
        )

    async def scrape(self, scraping_input: ScrapingInput) -> ScrapingOutput:
        url = str(scraping_input.url)
        payload = {
            "url": url,
            "formats": ["markdown", "html"],
            "onlyMainContent": True,
        }

        async with self._client_factory() as client:
            try:
                response = await client.post(_FIRECRAWL_SCRAPE_ENDPOINT, json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ScrapingRequestError(
                    f"Firecrawl devolveu HTTP {exc.response.status_code} para {url}"
                ) from exc
            except httpx.RequestError as exc:
                raise ScrapingRequestError(
                    f"Falha de rede ao chamar Firecrawl para {url}: {exc}"
                ) from exc

        data = response.json()
        result = data.get("data", {})
        markdown = result.get("markdown", "").strip()
        html = result.get("html", "").strip()
        metadata = result.get("metadata", {})

        if not markdown:
            raise ContentExtractionError(
                f"Firecrawl nao retornou conteudo Markdown utilizavel para {url}."
            )

        return ScrapingOutput(
            source_url=url,
            final_url=metadata.get("sourceURL", url),
            title=metadata.get("title", ""),
            raw_html=html,
            raw_text=markdown,
            status_code=metadata.get("statusCode", 200),
            content_type="text/html",
            method=self.method,
            metadata={
                "extraction_engine": "firecrawl",
                "firecrawl_language": metadata.get("language", ""),
                "firecrawl_og_title": metadata.get("ogTitle", ""),
            },
        )
