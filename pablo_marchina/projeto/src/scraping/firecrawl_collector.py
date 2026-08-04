from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from src.scraping.strategies import register

logger = logging.getLogger(__name__)

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v1"


@dataclass
class FirecrawlResult:
    url: str
    markdown: str
    html: str = ""
    title: str = ""
    description: str = ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None


def _firecrawl_scrape(url: str) -> FirecrawlResult:
    if not FIRECRAWL_API_KEY:
        return FirecrawlResult(url=url, markdown="", error="FIRECRAWL_API_KEY not set")

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{FIRECRAWL_BASE_URL}/scrape",
                json={"url": url, "formats": ["markdown", "html"]},
                headers={
                    "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            data = resp.json()
            if not data.get("success"):
                err = data.get("error", "unknown firecrawl error")
                return FirecrawlResult(url=url, markdown="", error=str(err))
            result_data = data.get("data", {})
            return FirecrawlResult(
                url=url,
                markdown=result_data.get("markdown", ""),
                html=result_data.get("html", ""),
                title=result_data.get("metadata", {}).get("title", ""),
                description=result_data.get("metadata", {}).get("description", ""),
            )
    except Exception as exc:
        logger.warning("FIRECRAWL_ERR  %s  %s", url, exc)
        return FirecrawlResult(url=url, markdown="", error=str(exc))


@register("firecrawl")
def collect_firecrawl(source: Any) -> FirecrawlResult | None:
    from src.scraping.source_registry import SourceRecord

    if not isinstance(source, SourceRecord):
        return None
    return _firecrawl_scrape(source.base_url)
