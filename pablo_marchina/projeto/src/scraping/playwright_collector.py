from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.scraping.strategies import register

logger = logging.getLogger(__name__)


@dataclass
class PlaywrightResult:
    url: str
    markdown: str
    html: str = ""
    title: str = ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None


def _crawl4ai_scrape(url: str, timeout: int = 30) -> PlaywrightResult:
    try:
        from crawl4ai import AsyncWebCrawler

        async def _run() -> PlaywrightResult:
            try:
                async with AsyncWebCrawler() as crawler:
                    result = await crawler.arun(url=url, bypass_cache=True, verbose=False)
                    return PlaywrightResult(
                        url=url,
                        markdown=result.markdown or "",
                        html=result.html or "",
                        title=getattr(result, "title", ""),
                    )
            except Exception as exc:
                return PlaywrightResult(url=url, markdown="", error=str(exc))

        return asyncio.run(_run())
    except ImportError:
        logger.warning("PLAYWRIGHT_SKIP  crawl4ai not installed — install with: pip install crawl4ai")
        return PlaywrightResult(url=url, markdown="", error="crawl4ai not installed")
    except Exception as exc:
        logger.warning("PLAYWRIGHT_ERR  %s  %s", url, exc)
        return PlaywrightResult(url=url, markdown="", error=str(exc))


@register("playwright")
def collect_playwright(source: Any) -> PlaywrightResult | None:
    from src.scraping.source_registry import SourceRecord

    if not isinstance(source, SourceRecord):
        return None
    return _crawl4ai_scrape(source.base_url)


@register("optional_playwright")
def collect_optional_playwright(source: Any) -> PlaywrightResult | None:
    from src.scraping.source_registry import SourceRecord

    if not isinstance(source, SourceRecord):
        return None
    return _crawl4ai_scrape(source.base_url)
