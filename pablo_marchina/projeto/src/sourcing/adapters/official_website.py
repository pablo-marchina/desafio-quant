from __future__ import annotations

from src.sourcing.adapters.base import EvidenceSpan, SourceResult
from src.sourcing.adapters.static_html import StaticHtmlAdapter


class OfficialWebsiteAdapter(StaticHtmlAdapter):
    """Collect content from a startup's official website.

    Adds a structured evidence span with the company name heuristic
    extracted from the HTML <title> tag.
    """

    source_type = "official_website"

    def collect(self, target: str) -> SourceResult:
        base_result = super().collect(target)
        if base_result.status != "collected" or not base_result.raw_text:
            return base_result

        import re

        title_match = re.search(r"<title[^>]*>([^<]+)</title>", base_result.raw_text, re.IGNORECASE)
        if title_match:
            company_name_hint = title_match.group(1).strip()
            extra = EvidenceSpan(
                text=f"Company name hint: {company_name_hint}",
                source_url=target,
                confidence=0.5,
            )
            return SourceResult(
                target=base_result.target,
                status=base_result.status,
                raw_text=base_result.raw_text,
                evidence_spans=base_result.evidence_spans + [extra],
                content_hash=base_result.content_hash,
            )
        return base_result
