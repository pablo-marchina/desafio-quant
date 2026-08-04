"""Estrategia de scraping para paginas que dependem de JavaScript."""

import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from apps.api.src.modules.scraping.application.dto import ScrapingInput, ScrapingOutput
from apps.api.src.modules.scraping.application.ports import Scraper
from apps.api.src.modules.scraping.application.scraping_limits import ScrapingLimits
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.domain.exceptions import (
    ScrapingLimitExceededError,
    ScrapingRequestError,
    UnsafeUrlError,
)
from apps.api.src.modules.scraping.infrastructure.security.url_guard import UrlGuard


@contextmanager
def _real_stdio() -> Iterator[None]:
    """Restaura sys.stdout/stderr originais durante o launch do Chromium.

    Dentro do scraper_worker (Dramatiq), o processo de trabalho substitui
    sys.stdout/stderr por um pipe entre processos usado so para encaminhar
    logs ao processo principal (``StreamablePipe``, em ``dramatiq/cli.py``).
    Esse pipe tem um ``fileno()`` valido, mas nao e' um handle herdavel pelo
    subprocesso que o Playwright cria internamente (driver Node + Chromium):
    no Windows isso falha com ``OSError: [Errno 9] Bad file descriptor``.
    ``sys.__stdout__``/``sys.__stderr__`` preservam os streams originais do
    processo, que sao herdaveis de verdade.

    Risco aceito: sys.stdout/stderr sao globais do processo, compartilhados
    entre as threads do worker (``--threads 4``). Uma linha de log de outra
    thread durante esta janela curta pode ir para o console em vez do pipe
    agregador — sem perda de dados, so o destino de uma linha pontual.
    """

    original_stdout, original_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.__stdout__ or original_stdout
    sys.stderr = sys.__stderr__ or original_stderr
    try:
        yield
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr


class PlaywrightScraper(Scraper):
    """Renderiza uma pagina em Chromium e extrai o conteudo final."""

    method = ScrapingMethod.PLAYWRIGHT

    def __init__(
        self,
        url_guard: UrlGuard,
        *,
        limits: ScrapingLimits | None = None,
        playwright_factory: Callable[[], Any] = async_playwright,
    ) -> None:
        self.url_guard = url_guard
        self.limits = limits or ScrapingLimits(timeout_seconds=30)
        self.playwright_factory = playwright_factory

    async def scrape(self, scraping_input: ScrapingInput) -> ScrapingOutput:
        """Executa JavaScript e devolve o formato padronizado da aplicacao."""

        await self.url_guard.validate(scraping_input.url)
        unsafe_error: UnsafeUrlError | None = None

        async def guard_request(route) -> None:
            """Bloqueia requisicoes do navegador para destinos inseguros."""

            nonlocal unsafe_error
            request_url = route.request.url

            # Recursos internos do navegador, como data: e blob:, nao realizam
            # acesso de rede e podem continuar sem validacao DNS.
            if urlparse(request_url).scheme not in {"http", "https"}:
                await route.continue_()
                return

            try:
                await self.url_guard.validate(request_url)
            except UnsafeUrlError as error:
                unsafe_error = error
                await route.abort("blockedbyclient")
                return

            await route.continue_()

        playwright_context = self.playwright_factory()
        entered_playwright_context = False
        try:
            # Spawn do driver Node + Chromium precisa de stdio real (ver
            # docstring de ``_real_stdio``); o resto da sessao usa a conexao
            # ja estabelecida e nao precisa do swap.
            with _real_stdio():
                playwright = await playwright_context.__aenter__()
                entered_playwright_context = True
                browser = await playwright.chromium.launch(headless=True)

            try:
                context = await browser.new_context(
                    user_agent=(
                        "AI-Venture-Radar/0.1 "
                        "(public-content-research; contact@example.com)"
                    )
                )
                await context.route("**/*", guard_request)
                page = await context.new_page()

                response = await page.goto(
                    scraping_input.url,
                    # Paginas modernas podem manter analytics e conexoes
                    # abertas indefinidamente. DOMContentLoaded evita que
                    # essas conexoes transformem uma coleta valida em timeout.
                    wait_until="domcontentloaded",
                    timeout=self.limits.timeout_seconds * 1000,
                )

                if unsafe_error is not None:
                    raise unsafe_error

                if response is None:
                    raise ScrapingRequestError(
                        "Playwright nao recebeu uma resposta HTTP da pagina."
                    )

                body = page.locator("body")
                await body.wait_for(
                    state="attached",
                    timeout=self.limits.timeout_seconds * 1000,
                )

                raw_html = await page.content()
                response_size = len(raw_html.encode("utf-8"))
                if response_size > self.limits.max_response_bytes:
                    raise ScrapingLimitExceededError(
                        "A pagina renderizada excede o limite de "
                        f"{self.limits.max_response_bytes} bytes."
                    )

                return ScrapingOutput(
                    source_url=scraping_input.url,
                    final_url=page.url,
                    title=await page.title(),
                    raw_html=raw_html,
                    raw_text=await body.inner_text(),
                    status_code=response.status,
                    content_type=(await response.all_headers()).get(
                        "content-type",
                        "",
                    ),
                    method=self.method,
                    metadata={
                        "response_bytes": response_size,
                        "browser": "chromium",
                        "javascript_rendered": True,
                    },
                )
            finally:
                await browser.close()
        except PlaywrightTimeoutError as error:
            raise ScrapingLimitExceededError(
                f"Playwright excedeu o timeout de {self.limits.timeout_seconds}s."
            ) from error
        except PlaywrightError as error:
            if unsafe_error is not None:
                raise unsafe_error from error

            raise ScrapingRequestError(
                f"Playwright nao conseguiu acessar a URL: {error}."
            ) from error
        finally:
            if entered_playwright_context:
                await playwright_context.__aexit__(None, None, None)
