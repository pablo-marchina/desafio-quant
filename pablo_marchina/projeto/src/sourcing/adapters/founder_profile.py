from __future__ import annotations

import re

from src.sourcing.adapters.base import EvidenceSpan, SourceResult
from src.sourcing.adapters.static_html import StaticHtmlAdapter

FOUNDER_PATTERNS: list[tuple[str, float]] = [
    (r"(?:founder|co-founder|ceo|cto|cfo|coo)[\s:;]+([A-Z][a-zà-ú]+(?:\s+[A-Z][a-zà-ú]+){1,3})", 0.8),
    (r"(?:liderado por|fundado por|lead by|founded by)[\s:;]+([A-Z][a-zà-ú]+(?:\s+[A-Z][a-zà-ú]+){1,3})", 0.7),
    (r'"name":\s*"([A-Z][a-zà-ú]+(?:\s+[A-Z][a-zà-ú]+){1,3})".*?"title":\s*"(?:founder|ceo|cto)', 0.9),
]

SOCIAL_LINK_PATTERNS: list[tuple[str, str]] = [
    (r"github\.com/([a-zA-Z0-9_-]+)", "github"),
    (r"linkedin\.com/in/([a-zA-Z0-9_-]+)", "linkedin"),
    (r"twitter\.com/([a-zA-Z0-9_]+)", "twitter"),
    (r"x\.com/([a-zA-Z0-9_]+)", "x"),
    (r"crunchbase\.com/person/([a-zA-Z0-9_-]+)", "crunchbase"),
    (r"angel\.co/([a-zA-Z0-9_-]+)", "angellist"),
]


def _extract_founders(text: str) -> list[dict]:
    """Extract potential founder names from text using regex patterns."""
    found: list[dict] = []
    seen = set()
    for pattern, confidence in FOUNDER_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            name = m.group(1).strip()
            if name.lower() not in seen and 5 <= len(name) <= 60:
                seen.add(name.lower())
                found.append({"name": name, "confidence": confidence, "matched_by": pattern[:30]})
    return found


def _extract_social_links(text: str) -> list[dict[str, str]]:
    """Extract founder-related social profile URLs."""
    links: list[dict[str, str]] = []
    seen = set()
    for pattern, platform in SOCIAL_LINK_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            handle = m.group(1)
            if handle.lower() not in seen:
                seen.add(handle.lower())
                links.append({"platform": platform, "handle": handle})
    return links


class FounderProfileAdapter(StaticHtmlAdapter):
    """Collect and extract founder information from public profiles.

    Scrapes the given URL (LinkedIn, GitHub, personal site, Crunchbase, etc.)
    and extracts founder names, titles, and social media links using regex
    patterns.
    """

    source_type = "founder_profile"

    def collect(self, target: str) -> SourceResult:
        base_result = super().collect(target)
        if base_result.status != "collected":
            return base_result

        text = base_result.raw_text
        founders = _extract_founders(text)
        social_links = _extract_social_links(text)

        extra_spans: list[EvidenceSpan] = []
        for f in founders:
            extra_spans.append(
                EvidenceSpan(
                    text=f"Founder: {f['name']} (confidence={f['confidence']})",
                    source_url=target,
                    confidence=f["confidence"],
                )
            )
        for link in social_links:
            extra_spans.append(
                EvidenceSpan(
                    text=f"Social: {link['platform']} handle={link['handle']}",
                    source_url=target,
                    confidence=0.6,
                )
            )

        return SourceResult(
            target=base_result.target,
            status=base_result.status,
            raw_text=base_result.raw_text,
            evidence_spans=base_result.evidence_spans + extra_spans,
            content_hash=base_result.content_hash,
        )
