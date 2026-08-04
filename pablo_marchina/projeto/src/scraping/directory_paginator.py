from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

import httpx

from src.scraping.source_registry import SourceRecord

logger = logging.getLogger(__name__)


def _query_param_page(base_url: str, param: str, max_pages: int = 20) -> list[str]:
    """Generate page URLs using a query parameter (``?page=N``)."""
    pages: list[str] = []
    sep = "&" if "?" in base_url else "?"
    for n in range(1, max_pages + 1):
        pages.append(f"{base_url}{sep}{param}={n}")
    return pages


def _infinite_scroll(base_url: str, selector: str, max_pages: int = 10) -> list[str]:
    """For infinite-scroll directories, just return the base URL.

    The scraping engine will need to handle JS rendering (Playwright).
    """
    return [base_url]


def _next_link(base_url: str, html: str, max_pages: int = 20,
               http_client: Callable[[str], Any] | None = None) -> list[str]:
    """Follow a 'next page' link pattern in HTML.

    Extracts ``<a rel="next" href="...">`` or ``<a class="next" href="...">``
    and follows it recursively.

    Args:
        base_url: Starting page URL.
        html: HTML of the first page (optional, used for next-link extraction).
        max_pages: Maximum pages to follow.
        http_client: Optional callable ``get(url) -> response`` that respects
            governed scraping policies. Falls back to ``httpx`` if not provided.
    """
    pages: list[str] = [base_url]
    current_url = base_url
    for _ in range(max_pages):
        try:
            if http_client is not None:
                resp = http_client(current_url)
            else:
                import os
                if os.getenv("APP_MODE", "").casefold() == "product":
                    raise RuntimeError("Direct directory pagination is disabled in APP_MODE=product; inject governed http_client.")
                resp = httpx.get(current_url, timeout=10, follow_redirects=True)
            status = resp.status_code if hasattr(resp, "status_code") else getattr(resp, "status", 0)
            if status != 200:
                break
            html_text = resp.text if hasattr(resp, "text") else (resp.content.decode("utf-8") if hasattr(resp, "content") else "")
            # Look for next-page link
            m = re.search(
                r'<(?:a|link)\s+[^>]*?(?:rel="next"|class="[^"]*next[^"]*")[^>]*?href="([^"]+)"',
                html_text,
                re.IGNORECASE,
            )
            if not m:
                break
            next_url = m.group(1)
            if not next_url.startswith("http"):
                from urllib.parse import urljoin

                next_url = urljoin(current_url, next_url)
            if next_url in pages:
                break  # avoid loops
            pages.append(next_url)
            current_url = next_url
        except Exception:
            break
    return pages


PAGE_STRATEGIES: dict[str, Any] = {
    "query_param_page": _query_param_page,
    "infinite_scroll": _infinite_scroll,
    "next_link": _next_link,
}


# ── Per-directory strategy registry ─────────────────────────────────────

DIRECTORY_CONFIG: dict[str, dict[str, Any]] = {
    "distrito_startup_programs": {"strategy": "query_param_page", "param": "pagina"},
    "cubo_ecosystem": {"strategy": "infinite_scroll", "selector": ".load-more"},
    "openstartups": {"strategy": "query_param_page", "param": "pagina"},
    "startse_media": {"strategy": "query_param_page", "param": "pagina"},
    "ace_startups_portfolio": {"strategy": "query_param_page", "param": "page"},
    "inovativa_startups": {"strategy": "query_param_page", "param": "pagina"},
    "bossa_invest_portfolio": {"strategy": "query_param_page", "param": "page"},
    "wow_aceleradora_ecosystem": {"strategy": "infinite_scroll", "selector": ".load-more"},
}


def paginate(source_id: str, base_url: str, html: str | None = None) -> list[str]:
    """Return all page URLs for a given directory source.

    Args:
        source_id: Source identifier (used to look up pagination strategy).
        base_url: Base URL of the directory.
        html: Optional HTML of the first page (used by ``next_link`` strategy).

    Returns:
        List of page URLs including the first page.
    """
    config = DIRECTORY_CONFIG.get(source_id)
    if config is None:
        return [base_url]  # fallback: no pagination

    strategy_name = config.get("strategy", "query_param_page")
    strategy_fn = PAGE_STRATEGIES.get(strategy_name)
    if strategy_fn is None:
        return [base_url]

    if strategy_name == "query_param_page":
        return strategy_fn(base_url, config.get("param", "page"))
    elif strategy_name == "infinite_scroll":
        return strategy_fn(base_url, config.get("selector", ""))
    elif strategy_name == "next_link":
        return strategy_fn(base_url, html or "")
    return [base_url]


def extract_startup_links(source_id: str, html: str) -> list[dict[str, str]]:
    """Extract startup name + URL from a directory page, keyed by source_id."""
    try:
        from src.sourcing.adapters.directory import _extract_startup_links
    except ImportError as exc:
        logger.error("Cannot import _extract_startup_links (circular dependency?): %s", exc)
        return []

    # delegate to the sourcing-layer extractor
    base_url = ""
    return _extract_startup_links(html, base_url)
