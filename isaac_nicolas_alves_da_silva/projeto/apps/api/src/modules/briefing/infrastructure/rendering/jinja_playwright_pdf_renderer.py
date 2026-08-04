"""Renderiza o Markdown do briefing em PDF via Jinja2 + Chromium headless."""

import asyncio
import sys
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from apps.api.src.modules.briefing.application.dto import BriefingView
from apps.api.src.modules.briefing.application.ports import BriefingDocumentRenderer
from apps.api.src.modules.briefing.domain.exceptions import BriefingRenderingError

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class JinjaPlaywrightPdfRenderer(BriefingDocumentRenderer):
    """Markdown -> HTML (Jinja2 + markdown) -> PDF (Playwright/Chromium).

    Links Markdown (``[texto](url)``) ja viram ``<a href>`` na conversao -
    isso e' o que preserva as citacoes do briefing no PDF exportado, sem
    tratamento especial. Sem dependencia nativa nova (Pango/Cairo/GTK que
    o weasyprint exigiria): ``playwright`` ja e' dependencia do projeto e
    ja funciona neste ambiente (mesmo binario usado em
    ``scraping/infrastructure/scrapers/playwright_scraper.py``).
    """

    def __init__(self) -> None:
        self._jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)))

    async def render_pdf(self, briefing: BriefingView) -> bytes:
        body_html = markdown.markdown(briefing.content, extensions=["extra"])
        template = self._jinja_env.get_template("briefing.html.jinja")
        html = template.render(
            body=body_html,
            startup_id=briefing.startup_id,
            generated_at=briefing.generated_at.isoformat(),
        )

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, _render_pdf_in_dedicated_loop, html)
        except PlaywrightError as error:
            raise BriefingRenderingError(
                f"Falha ao renderizar o briefing em PDF: {error}."
            ) from error


def _render_pdf_in_dedicated_loop(html: str) -> bytes:
    """Roda o Playwright num event loop novo, dedicado a esta thread.

    No Windows, o loop do processo que esta chamando (ex: SelectorEventLoop
    sob certas configuracoes de ``uvicorn --reload``) pode nao suportar
    ``create_subprocess_exec``, que o driver do Playwright precisa para
    abrir o Chromium (``NotImplementedError`` em
    ``BaseEventLoop._make_subprocess_transport``). So o ``ProactorEventLoop``
    suporta subprocess no Windows. Criar um loop dedicado numa thread
    separada (via ``run_in_executor``) evita depender da politica de loop
    do processo principal - funciona independente de como a app foi
    iniciada (uvicorn com/sem --reload, workers, etc.).
    """

    loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_render_pdf_async(html))
    finally:
        loop.close()


async def _render_pdf_async(html: str) -> bytes:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.set_content(html, wait_until="load")
            return await page.pdf(format="A4")
        finally:
            await browser.close()
