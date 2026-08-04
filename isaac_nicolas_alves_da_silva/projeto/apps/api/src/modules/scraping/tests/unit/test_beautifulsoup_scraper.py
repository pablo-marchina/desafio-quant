"""Testes da implementação concreta do scraper BeautifulSoup."""

import httpx
import pytest

from apps.api.src.modules.scraping.application.dto import ScrapingInput
from apps.api.src.modules.scraping.application.scraping_limits import ScrapingLimits
from apps.api.src.modules.scraping.domain.exceptions import (
    ScrapingLimitExceededError,
    UnsafeUrlError,
)
from apps.api.src.modules.scraping.infrastructure.scrapers.beautifulsoup_scraper import (
    BeautifulSoupScraper,
)


class RecordingUrlGuard:
    """Guarda as URLs validadas sem realizar resolução DNS real."""

    def __init__(self) -> None:
        self.validated_urls: list[str] = []

    async def validate(self, url: str) -> None:
        self.validated_urls.append(url)


def make_client_factory(
    handler,
):
    """Cria uma factory de clientes usando respostas HTTP simuladas."""

    def factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    return factory


@pytest.mark.anyio
async def test_extracts_visible_text_and_validates_source_url() -> None:
    """O scraper deve extrair texto e validar a URL antes do acesso."""

    html = """
    <html>
      <head>
        <title>Startup Exemplo</title>
        <style>body { color: red; }</style>
      </head>
      <body>
        <h1>Inteligência Artificial</h1>
        <p>Produto para empresas.</p>
        <script>alert("não deve aparecer")</script>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=html,
            request=request,
        )

    guard = RecordingUrlGuard()
    scraper = BeautifulSoupScraper(
        url_guard=guard,
        client_factory=make_client_factory(handler),
    )

    output = await scraper.scrape(ScrapingInput(url="https://example.com"))

    assert output.title == "Startup Exemplo"
    assert "Inteligência Artificial" in output.raw_text
    assert "Produto para empresas." in output.raw_text
    assert "alert" not in output.raw_text
    assert "color: red" not in output.raw_text
    assert guard.validated_urls == ["https://example.com"]


@pytest.mark.anyio
async def test_response_larger_than_strategy_limit_is_recoverable() -> None:
    """Resposta grande demais deve permitir fallback para outra estratégia."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            text="<html>conteúdo maior que dez bytes</html>",
            request=request,
        )

    scraper = BeautifulSoupScraper(
        url_guard=RecordingUrlGuard(),
        limits=ScrapingLimits(max_response_bytes=10),
        client_factory=make_client_factory(handler),
    )

    with pytest.raises(ScrapingLimitExceededError, match="excede o limite"):
        await scraper.scrape(ScrapingInput(url="https://example.com"))


@pytest.mark.anyio
async def test_timeout_is_translated_to_recoverable_limit_error() -> None:
    """Timeout do httpx não deve vazar como detalhe técnico da biblioteca."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Tempo esgotado.", request=request)

    scraper = BeautifulSoupScraper(
        url_guard=RecordingUrlGuard(),
        limits=ScrapingLimits(timeout_seconds=2),
        client_factory=make_client_factory(handler),
    )

    with pytest.raises(ScrapingLimitExceededError, match="timeout de 2"):
        await scraper.scrape(ScrapingInput(url="https://example.com"))


@pytest.mark.anyio
async def test_blocks_unsafe_redirect_before_requesting_destination() -> None:
    """Redirect para IP privado deve ser bloqueado antes do segundo acesso."""

    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(
            status_code=302,
            headers={"location": "http://192.168.1.10/admin"},
            request=request,
        )

    class PrivateRedirectGuard(RecordingUrlGuard):
        async def validate(self, url: str) -> None:
            await super().validate(url)
            if url == "http://192.168.1.10/admin":
                raise UnsafeUrlError("Destino privado bloqueado.")

    scraper = BeautifulSoupScraper(
        url_guard=PrivateRedirectGuard(),
        client_factory=make_client_factory(handler),
    )

    with pytest.raises(UnsafeUrlError, match="Destino privado"):
        await scraper.scrape(ScrapingInput(url="https://example.com"))

    # Somente a URL pública inicial pode ter sido requisitada.
    assert requested_urls == ["https://example.com"]
