"""Estrategia que extrai o conteudo principal de paginas HTML."""

import asyncio
from collections.abc import Callable

from trafilatura import extract

from apps.api.src.modules.scraping.application.dto import ScrapingInput, ScrapingOutput
from apps.api.src.modules.scraping.application.ports import Scraper
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.domain.exceptions import ContentExtractionError


TrafilaturaExtractor = Callable[..., str | None]


class TrafilaturaScraper(Scraper):
    """Remove menus e rodapes do HTML coletado por outra estrategia."""

    method = ScrapingMethod.TRAFILATURA

    def __init__(
        self,
        source_scraper: Scraper,
        *,
        extractor: TrafilaturaExtractor = extract,
    ) -> None:
        self.source_scraper = source_scraper
        self.extractor = extractor

    async def scrape(self, scraping_input: ScrapingInput) -> ScrapingOutput:
        """Coleta HTML seguro e extrai somente seu conteudo principal."""

        source_output = await self.source_scraper.scrape(scraping_input)

        # Trafilatura e sincrona. A thread evita bloquear o event loop usado
        # pela API e pelos workers assincronos.
        extracted_text = await asyncio.to_thread(
            self.extractor,
            source_output.raw_html,
            output_format="txt",
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )

        if not extracted_text or not extracted_text.strip():
            raise ContentExtractionError(
                "Trafilatura nao encontrou conteudo principal utilizavel."
            )

        return ScrapingOutput(
            source_url=source_output.source_url,
            final_url=source_output.final_url,
            title=source_output.title,
            raw_html=source_output.raw_html,
            raw_text=extracted_text.strip(),
            status_code=source_output.status_code,
            content_type=source_output.content_type,
            method=self.method,
            metadata={
                **source_output.metadata,
                "extraction_engine": "trafilatura",
                "main_content_extracted": True,
            },
        )
