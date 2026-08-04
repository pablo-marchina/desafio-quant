from __future__ import annotations

from src.sourcing.adapters.base import SourceResult
from src.sourcing.adapters.static_html import StaticHtmlAdapter


class DynamicPageAdapter(StaticHtmlAdapter):
    """Collect JavaScript-heavy pages using Playwright (headless browser).

    Uses ``collector_type="playwright"`` so the governed scraping pipeline
    delegates to crawl4ai for rendering.
    """

    source_type = "dynamic_page"
    _default_collector_type = "playwright"

    def collect(self, target: str) -> SourceResult:
        return super().collect(target)
