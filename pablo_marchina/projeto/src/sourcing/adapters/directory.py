from __future__ import annotations

from typing import Any

from src.sourcing.adapters.base import EvidenceSpan, SourceResult
from src.sourcing.adapters.static_html import StaticHtmlAdapter


def _extract_startup_links(html: str, base_url: str) -> list[dict[str, str]]:
    """Naive extraction of startup links from directory HTML.

    Looks for common directory HTML patterns:
    - ``<a href="...">name</a>`` inside list/grid items
    - ``<h3><a href="...">name</a></h3>``
    - Table rows with company names
    """
    import re

    entries: list[dict[str, str]] = []

    # Pattern 1: <a href="...">text</a> where text looks like a company name
    for match in re.finditer(r'<a\s+href="([^"]+)"[^>]*>([^<]{3,80})</a>', html):
        url = match.group(1).strip()
        name = match.group(2).strip()
        # Filter out navigation, social, login links
        if any(
            skip in url.lower()
            for skip in ["#", "javascript:", "login", "signup", "mailto:", "tel:", "facebook", "twitter", "linkedin"]
        ):
            continue
        if name and url and 3 <= len(name) <= 80:
            full_url = url if url.startswith("http") else base_url.rstrip("/") + "/" + url.lstrip("/")
            entries.append({"name": name, "url": full_url})

    return entries


class DirectoryAdapter(StaticHtmlAdapter):
    """Collect startup listings from accelerator / ecosystem directories.

    In addition to extracting page text, parses the HTML for startup
    links (name + URL) and returns them as structured evidence spans.
    """

    source_type = "startup_directory"

    def collect(self, target: str) -> SourceResult:
        base_result = super().collect(target)
        if base_result.status != "collected":
            return base_result

        startup_entries = _extract_startup_links(base_result.raw_text, target)

        extra_spans = [
            EvidenceSpan(
                text=f"Startup: {e['name']}",
                source_url=e["url"],
                confidence=0.5,
            )
            for e in startup_entries
        ]

        return SourceResult(
            target=base_result.target,
            status=base_result.status,
            raw_text=base_result.raw_text,
            evidence_spans=base_result.evidence_spans + extra_spans,
            content_hash=base_result.content_hash,
        )
