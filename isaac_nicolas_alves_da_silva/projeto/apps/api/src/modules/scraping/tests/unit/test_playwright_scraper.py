"""Testes do PlaywrightScraper sem abrir um navegador real."""

import sys

import pytest

from apps.api.src.modules.scraping.application.dto import ScrapingInput
from apps.api.src.modules.scraping.application.scraping_limits import ScrapingLimits
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.domain.exceptions import (
    ScrapingLimitExceededError,
    UnsafeUrlError,
)
from apps.api.src.modules.scraping.infrastructure.scrapers.playwright_scraper import (
    PlaywrightScraper,
)


class RecordingUrlGuard:
    """Registra destinos e pode bloquear um endereco especifico."""

    def __init__(self, blocked_url: str | None = None) -> None:
        self.blocked_url = blocked_url
        self.validated_urls: list[str] = []

    async def validate(self, url: str) -> None:
        self.validated_urls.append(url)
        if url == self.blocked_url:
            raise UnsafeUrlError("Destino privado bloqueado.")


class FakeRoute:
    def __init__(self, url: str) -> None:
        self.request = type("Request", (), {"url": url})()
        self.was_aborted = False

    async def continue_(self) -> None:
        return None

    async def abort(self, reason: str) -> None:
        self.was_aborted = True


class FakeResponse:
    status = 200

    async def all_headers(self) -> dict[str, str]:
        return {"content-type": "text/html; charset=utf-8"}


class FakeLocator:
    async def wait_for(self, **kwargs) -> None:
        return None

    async def inner_text(self) -> str:
        return "Conteudo carregado por JavaScript com inteligencia artificial."


class FakePage:
    url = "https://example.com/final"

    def __init__(self, context, requested_urls: list[str]) -> None:
        self.context = context
        self.requested_urls = requested_urls

    async def goto(self, url: str, **kwargs):
        for requested_url in self.requested_urls:
            await self.context.route_handler(FakeRoute(requested_url))
        return FakeResponse()

    async def content(self) -> str:
        return "<html><body>Conteudo renderizado</body></html>"

    async def title(self) -> str:
        return "Pagina dinamica"

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator()


class FakeContext:
    def __init__(self, requested_urls: list[str]) -> None:
        self.requested_urls = requested_urls
        self.route_handler = None

    async def route(self, pattern: str, handler) -> None:
        self.route_handler = handler

    async def new_page(self) -> FakePage:
        return FakePage(self, self.requested_urls)


class FakeBrowser:
    def __init__(self, requested_urls: list[str]) -> None:
        self.requested_urls = requested_urls
        self.was_closed = False

    async def new_context(self, **kwargs) -> FakeContext:
        return FakeContext(self.requested_urls)

    async def close(self) -> None:
        self.was_closed = True


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser

    async def launch(self, **kwargs) -> FakeBrowser:
        return self.browser


class FakePlaywrightContext:
    def __init__(self, requested_urls: list[str]) -> None:
        self.browser = FakeBrowser(requested_urls)
        self.chromium = FakeChromium(self.browser)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exception_type, exception, traceback) -> None:
        return None


def make_playwright_factory(requested_urls: list[str]):
    return lambda: FakePlaywrightContext(requested_urls)


@pytest.mark.anyio
async def test_renders_javascript_content_and_returns_standard_output() -> None:
    """Playwright deve devolver o mesmo ScrapingOutput das outras estrategias."""

    guard = RecordingUrlGuard()
    scraper = PlaywrightScraper(
        url_guard=guard,
        playwright_factory=make_playwright_factory(["https://example.com"]),
    )

    output = await scraper.scrape(ScrapingInput(url="https://example.com"))

    assert output.method is ScrapingMethod.PLAYWRIGHT
    assert output.title == "Pagina dinamica"
    assert output.final_url == "https://example.com/final"
    assert output.metadata["javascript_rendered"] is True
    assert guard.validated_urls == [
        "https://example.com",
        "https://example.com",
    ]


@pytest.mark.anyio
async def test_blocks_unsafe_browser_subrequest() -> None:
    """JavaScript nao pode usar o navegador para acessar uma rede privada."""

    private_url = "http://192.168.1.10/admin"
    scraper = PlaywrightScraper(
        url_guard=RecordingUrlGuard(blocked_url=private_url),
        playwright_factory=make_playwright_factory(
            ["https://example.com", private_url]
        ),
    )

    with pytest.raises(UnsafeUrlError, match="Destino privado"):
        await scraper.scrape(ScrapingInput(url="https://example.com"))


@pytest.mark.anyio
async def test_restores_real_stdio_only_during_browser_launch() -> None:
    """sys.stdout/stderr devem ser os originais so durante o launch do Chromium.

    Simula o cenario do scraper_worker (Dramatiq), que substitui
    sys.stdout/stderr por um pipe entre processos antes de qualquer scraping
    rodar (ver docstring de ``_real_stdio`` no modulo da implementacao).
    """

    class FakeLoggingPipe:
        def fileno(self) -> int:
            raise OSError("nao herdavel")

    fake_pipe = FakeLoggingPipe()
    captured: dict[str, object] = {}

    class CapturingChromium(FakeChromium):
        async def launch(self, **kwargs) -> FakeBrowser:
            captured["stdout"] = sys.stdout
            captured["stderr"] = sys.stderr
            return await super().launch(**kwargs)

    playwright_context = FakePlaywrightContext(["https://example.com"])
    playwright_context.chromium = CapturingChromium(playwright_context.browser)

    original_stdout, original_stderr = sys.stdout, sys.stderr
    sys.stdout = fake_pipe
    sys.stderr = fake_pipe
    try:
        scraper = PlaywrightScraper(
            url_guard=RecordingUrlGuard(),
            playwright_factory=lambda: playwright_context,
        )
        await scraper.scrape(ScrapingInput(url="https://example.com"))

        assert captured["stdout"] is sys.__stdout__
        assert captured["stderr"] is sys.__stderr__
        # Restaurado para o pipe de log assim que o launch termina.
        assert sys.stdout is fake_pipe
        assert sys.stderr is fake_pipe
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr


@pytest.mark.anyio
async def test_rendered_html_respects_response_size_limit() -> None:
    """DOM renderizado grande demais deve permitir fallback futuro."""

    scraper = PlaywrightScraper(
        url_guard=RecordingUrlGuard(),
        limits=ScrapingLimits(max_response_bytes=10),
        playwright_factory=make_playwright_factory(["https://example.com"]),
    )

    with pytest.raises(ScrapingLimitExceededError, match="renderizada excede"):
        await scraper.scrape(ScrapingInput(url="https://example.com"))
