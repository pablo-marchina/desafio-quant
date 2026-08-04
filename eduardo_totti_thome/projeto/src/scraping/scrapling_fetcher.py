"""Busca o HTML bruto de uma URL usando o Scrapling.

O Scrapling cuida do fetch + parsing + bypass de anti-bot. Aqui usamos o modo
HTTP simples (`Fetcher`), que não precisa de navegador. Modos mais pesados
(stealth/dinâmico) ficam para quando algum site exigir.
"""

from __future__ import annotations

from scrapling.fetchers import Fetcher

DEFAULT_TIMEOUT = 30


def fetch_html(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Baixa a página e devolve o HTML bruto como string.

    Levanta RuntimeError se o status HTTP não for 2xx (ex.: 404, 403, 500).
    """
    page = Fetcher.get(url, timeout=timeout)
    if not 200 <= page.status < 300:
        raise RuntimeError(f"Falha ao buscar {url}: status HTTP {page.status}")
    return str(page.html_content)


def fetch_html_browser(url: str, timeout_ms: int = 60000) -> str:
    """Baixa a página renderizando JavaScript num navegador (para SPAs).

    Usa o StealthyFetcher do Scrapling (navegador real + anti-bot). É lento (abre um
    navegador), então serve só de FALLBACK quando o fetch HTTP simples volta vazio.
    Exige o navegador instalado ('uv run scrapling install'); sem ele, levanta exceção
    (que o coletor trata, mantendo o resultado do fetch HTTP).
    """
    from scrapling.fetchers import StealthyFetcher

    page = StealthyFetcher.fetch(url, headless=True, timeout=timeout_ms)
    if not 200 <= page.status < 300:
        raise RuntimeError(f"Falha ao buscar {url} (navegador): status HTTP {page.status}")
    return str(page.html_content)
