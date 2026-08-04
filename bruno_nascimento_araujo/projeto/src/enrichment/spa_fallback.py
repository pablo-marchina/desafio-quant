"""Fallback para paginas renderizadas por JavaScript (SPAs).

Quando o parsing estatico de um candidato retorna vazio (provavel render JS),
tentamos Crawl4AI (import lazy/opcional) para extrair Markdown limpo. Se a lib
nao estiver instalada ou falhar, caimos no parsing estatico via BeautifulSoup.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from ..http_client import PoliteFetcher
from ..logging_conf import get_logger

logger = get_logger("spa")

_crawl4ai_available: bool | None = None  # cache do probe de import


def _probe_crawl4ai() -> bool:
    global _crawl4ai_available
    if _crawl4ai_available is None:
        try:
            import crawl4ai  # noqa: F401

            _crawl4ai_available = True
        except ImportError:
            _crawl4ai_available = False
            logger.warning(
                "crawl4ai ausente: SPAs usarao fallback estatico (BeautifulSoup)."
            )
    return _crawl4ai_available


_CRAWL4AI_TIMEOUT = 30  # segundos maximos para renderizacao de SPA via Playwright


async def _fetch_with_crawl4ai(url: str) -> str | None:
    import asyncio

    try:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler(verbose=False) as crawler:
            # Timeout explicito: sem isso, SPAs com JS infinito travam o pipeline.
            result = await asyncio.wait_for(
                crawler.arun(url=url),
                timeout=_CRAWL4AI_TIMEOUT,
            )
            if result and getattr(result, "markdown", None):
                logger.debug("SPA via crawl4ai: %s", url)
                return result.markdown
    except asyncio.TimeoutError:
        logger.warning("crawl4ai timeout (%ds) em %s — abortando SPA.", _CRAWL4AI_TIMEOUT, url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("crawl4ai falhou em %s: %s", url, exc)
    return None


async def _fetch_static(url: str, fetcher: PoliteFetcher) -> str | None:
    html = await fetcher.get_text(url)
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


async def fetch_clean(url: str, fetcher: PoliteFetcher) -> str | None:
    """Retorna texto/markdown limpo da pagina, com fallback automatico."""
    if _probe_crawl4ai():
        md = await _fetch_with_crawl4ai(url)
        if md:
            return md
    return await _fetch_static(url, fetcher)
