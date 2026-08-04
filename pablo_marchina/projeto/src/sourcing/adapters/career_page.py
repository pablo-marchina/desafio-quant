from __future__ import annotations

from src.sourcing.adapters.base import SourceResult
from src.sourcing.adapters.static_html import StaticHtmlAdapter

CAREER_SIGNALS = {
    "about",
    "team",
    "jobs",
    "careers",
    "join-us",
    "join_us",
    "work-with-us",
    "work_with_us",
    "working-at",
    "working_at",
    "life",
    "people",
}


class CareerPageAdapter(StaticHtmlAdapter):
    """Collect careers/jobs pages from startup websites.

    Inherits caching, rate limiting, robots compliance from the governed
    scraping pipeline via ``StaticHtmlAdapter``.
    """

    source_type = "careers"

    def _is_relevant_page(self, url: str) -> bool:
        """Check whether *url* looks like a career-related page."""
        path = url.split("?")[0].rstrip("/").lower()
        last_segment = path.rsplit("/", 1)[-1]
        return last_segment in CAREER_SIGNALS

    def collect(self, target: str) -> SourceResult:
        result = super().collect(target)
        if result.status == "collected" and not self._is_relevant_page(target):
            return SourceResult(
                target=target,
                status="skipped",
                raw_text="",
                error="Page does not appear to be a careers/jobs page",
            )
        return result
