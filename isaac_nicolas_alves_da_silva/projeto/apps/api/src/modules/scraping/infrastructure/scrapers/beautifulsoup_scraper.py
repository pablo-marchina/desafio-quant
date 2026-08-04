"""Estratégia de scraping para páginas com HTML estático."""

from collections.abc import Callable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from apps.api.src.modules.scraping.application.dto import ScrapingInput, ScrapingOutput
from apps.api.src.modules.scraping.application.ports import Scraper
from apps.api.src.modules.scraping.application.scraping_limits import ScrapingLimits
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.domain.exceptions import (
    ScrapingLimitExceededError,
    ScrapingRequestError,
)
from apps.api.src.modules.scraping.infrastructure.security.url_guard import UrlGuard


class BeautifulSoupScraper(Scraper):
    """Baixa HTML por HTTP e extrai seu texto visível básico.

    BeautifulSoup apenas interpreta HTML. Quem realiza a requisição é o
    ``httpx.AsyncClient``. Mantemos essas responsabilidades explícitas porque,
    futuramente, outros scrapers poderão utilizar Playwright ou APIs externas.
    """

    method = ScrapingMethod.BEAUTIFULSOUP

    def __init__(
        self,
        url_guard: UrlGuard,
        *,
        limits: ScrapingLimits | None = None,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self.url_guard = url_guard
        self.limits = limits or ScrapingLimits()

        # A factory injetável permite usar um cliente HTTP falso nos testes.
        self.client_factory = client_factory or self._create_default_client

    def _create_default_client(self) -> httpx.AsyncClient:
        """Cria o cliente usado em execução real."""

        return httpx.AsyncClient(
            timeout=self.limits.timeout_seconds,
            # Redirects são seguidos manualmente para validar cada destino com
            # UrlGuard antes que uma nova requisição seja realizada.
            follow_redirects=False,
            headers={
                "User-Agent": (
                    "AI-Venture-Radar/0.1 "
                    "(public-content-research; contact@example.com)"
                )
            },
        )

    async def scrape(self, scraping_input: ScrapingInput) -> ScrapingOutput:
        """Valida a URL, baixa o HTML e devolve o formato da aplicação."""

        await self.url_guard.validate(scraping_input.url)

        try:
            async with self.client_factory() as client:
                response = await self._get_following_safe_redirects(
                    client,
                    scraping_input.url,
                )
        except httpx.TimeoutException as error:
            raise ScrapingLimitExceededError(
                f"BeautifulSoup excedeu o timeout de {self.limits.timeout_seconds}s."
            ) from error
        except httpx.RequestError as error:
            raise ScrapingRequestError(
                f"BeautifulSoup não conseguiu acessar a URL: {error}."
            ) from error

        raw_html = response.text
        response_size = len(response.content)
        if response_size > self.limits.max_response_bytes:
            raise ScrapingLimitExceededError(
                "A resposta excede o limite de "
                f"{self.limits.max_response_bytes} bytes."
            )

        title, raw_text = self._extract_content(raw_html)

        return ScrapingOutput(
            source_url=scraping_input.url,
            final_url=str(response.url),
            title=title,
            raw_html=raw_html,
            raw_text=raw_text,
            status_code=response.status_code,
            content_type=response.headers.get("content-type", ""),
            method=self.method,
            metadata={
                "response_bytes": response_size,
                "encoding": response.encoding,
            },
        )

    async def _get_following_safe_redirects(
        self,
        client: httpx.AsyncClient,
        initial_url: str,
    ) -> httpx.Response:
        """Segue redirects somente depois de validar cada URL de destino."""

        current_url = initial_url

        # A primeira requisição não conta como redirect. Por isso permitimos
        # max_redirects + 1 requisições no total.
        for redirect_count in range(self.limits.max_redirects + 1):
            response = await client.get(current_url)

            if not response.is_redirect:
                return response

            if redirect_count >= self.limits.max_redirects:
                raise ScrapingLimitExceededError(
                    "A página excedeu o limite de "
                    f"{self.limits.max_redirects} redirects."
                )

            location = response.headers.get("location")
            if not location:
                raise ScrapingRequestError(
                    "A resposta informou redirect sem fornecer o destino."
                )

            # urljoin também transforma redirects relativos, como /sobre, em
            # uma URL absoluta baseada na página atual.
            next_url = urljoin(str(response.url), location)

            # Esta validação acontece antes da próxima chamada client.get().
            await self.url_guard.validate(next_url)
            current_url = next_url

        raise ScrapingLimitExceededError(
            f"A página excedeu o limite de {self.limits.max_redirects} redirects."
        )

    @staticmethod
    def _extract_content(raw_html: str) -> tuple[str | None, str]:
        """Extrai título e texto básico sem realizar limpeza profunda."""

        soup = BeautifulSoup(raw_html, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else None

        # Esses elementos não representam conteúdo textual útil da página.
        for element in soup(["script", "style", "noscript", "template"]):
            element.decompose()

        # O separador preserva limites entre blocos; ``strip`` remove espaços
        # extras de cada trecho antes da união.
        raw_text = soup.get_text(separator="\n", strip=True)

        return title, raw_text
