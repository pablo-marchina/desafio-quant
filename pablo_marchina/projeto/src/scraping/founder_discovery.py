from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_FOUNDER_NAME_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"(?:founder|co-founder|cofounder|CEO|CTO)[\s:;]+([A-Z][a-zà-ú]+(?:\s+[A-Z][a-zà-ú]+)+)", re.IGNORECASE), 0.8),
    (re.compile(r"(?:fundador|co-fundador|sócio|sócia)[\s:;]+([A-Z][a-zà-ú]+(?:\s+[A-Z][a-zà-ú]+)+)", re.IGNORECASE), 0.7),
    (re.compile(r"\"([A-Z][a-zà-ú]+(?:\s+[A-Z][a-zà-ú]+)+)\".*(?:founder|CEO|CTO)", re.IGNORECASE), 0.6),
    (re.compile(r"(?:leadership|team|equipe)[\s:;]*\n.*([A-Z][a-zà-ú]+(?:\s+[A-Z][a-zà-ú]+)+)", re.IGNORECASE), 0.4),
]

_SOCIAL_PATTERNS: dict[str, re.Pattern] = {
    "github": re.compile(r"github\.com/([a-zA-Z0-9_-]+)"),
    "linkedin": re.compile(r"linkedin\.com/in/([a-zA-Z0-9_-]+)"),
    "twitter": re.compile(r"twitter\.com/([a-zA-Z0-9_]+)"),
    "crunchbase": re.compile(r"crunchbase\.com/person/([a-zA-Z0-9_-]+)"),
}

_SOCIAL_CONTEXT_WINDOW = 500  # characters around founder name to search for social links


@dataclass
class FounderCandidate:
    name: str
    confidence: float
    role: str = ""
    social_links: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "confidence": self.confidence,
            "role": self.role,
            "social_links": self.social_links,
        }


class FounderDiscovery:
    """Extract founder names and social links from scraped content."""

    def extract(self, text: str, html: str | None = None) -> list[FounderCandidate]:
        candidates: list[FounderCandidate] = []
        seen: set[str] = set()

        for pattern, confidence in _FOUNDER_NAME_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                if name.lower() not in seen:
                    seen.add(name.lower())
                    role = self._infer_role(text, name)
                    candidates.append(FounderCandidate(
                        name=name,
                        confidence=confidence,
                        role=role,
                    ))

        for candidate in candidates:
            # Extract social links from the context AROUND this founder's name,
            # not from the entire page text, to avoid false attribution.
            candidate.social_links = self._extract_social_links(text, candidate.name)

        return candidates

    def _infer_role(self, text: str, name: str) -> str:
        context_window = 200
        idx = text.lower().find(name.lower())
        if idx == -1:
            return ""
        start = max(0, idx - context_window)
        end = min(len(text), idx + len(name) + context_window)
        context = text[start:end]

        role_patterns = [
            (r"CEO|Chief Executive Officer", "CEO"),
            (r"CTO|Chief Technology Officer", "CTO"),
            (r"COO|Chief Operating Officer", "COO"),
            (r"founder|co-founder|fundador", "Founder"),
            (r"CRO|Chief Revenue Officer", "CRO"),
            (r"CMO|Chief Marketing Officer", "CMO"),
            (r"CFO|Chief Financial Officer", "CFO"),
            (r"Chief [A-Z][a-z]+ Officer", "Executive"),
        ]
        for pat, role in role_patterns:
            if re.search(pat, context, re.IGNORECASE):
                return role
        return ""

    def _extract_social_links(self, text: str, name: str) -> dict[str, str]:
        """Extract social links found near *name* in *text*.

        Searches only within a context window around the first occurrence of
        *name* to avoid attributing links from unrelated parts of the page.
        """
        links: dict[str, str] = {}
        idx = text.lower().find(name.lower())
        if idx == -1:
            return links
        start = max(0, idx - _SOCIAL_CONTEXT_WINDOW)
        end = min(len(text), idx + len(name) + _SOCIAL_CONTEXT_WINDOW)
        context = text[start:end]

        for platform, pattern in _SOCIAL_PATTERNS.items():
            for match in pattern.finditer(context):
                handle = match.group(1)
                links[platform] = handle
        return links
