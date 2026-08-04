from __future__ import annotations

import difflib
import logging
import re
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Significance(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SectionChange:
    """Represents a changed section of text between two scraping runs."""

    def __init__(self, old_text: str, new_text: str, section_type: str = "unknown"):
        self.old_text = old_text
        self.new_text = new_text
        self.section_type = section_type

    def __repr__(self) -> str:
        return f"SectionChange(type={self.section_type}, old={len(self.old_text)}ch -> new={len(self.new_text)}ch)"


class ChangeReport:
    """Result of comparing two scraping runs for a single URL."""

    def __init__(
        self,
        changed: bool,
        sections_changed: list[SectionChange] | None = None,
        significance: Significance = Significance.LOW,
    ):
        self.changed = changed
        self.sections_changed = sections_changed or []
        self.significance = significance

    def __repr__(self) -> str:
        return f"ChangeReport(changed={self.changed}, sig={self.significance}, sections={len(self.sections_changed)})"


CRITICAL_SIGNAL_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(?:acquired|acquisition|merged|merger)\b.*\b(?:closed|completed|announced)\b", re.IGNORECASE),
    re.compile(r"\b(?:series\s*[cdefgh]|série\s*[cdefgh])\b", re.IGNORECASE),
    re.compile(r"\b(?:IPO|initial public offering)\b", re.IGNORECASE),
    re.compile(r"\b(?:unicorn|billion.*valuation|valuation.*billion)\b", re.IGNORECASE),
]

HIGH_SIGNAL_PATTERNS: list[re.Pattern] = [
    re.compile(r"\braised\b.*\$", re.IGNORECASE),
    re.compile(r"\bsérie\s*[a-z]\b", re.IGNORECASE),
    re.compile(r"\bseed\b.*\$", re.IGNORECASE),
    re.compile(r"\bfunding\b", re.IGNORECASE),
    re.compile(r"\binvestimento\b", re.IGNORECASE),
    re.compile(r"\brodada\b", re.IGNORECASE),
    re.compile(r"\bmillion\b", re.IGNORECASE),
    re.compile(r"\bacquisition\b", re.IGNORECASE),
    re.compile(r"\baquisição\b", re.IGNORECASE),
    re.compile(r"\bIPO\b", re.IGNORECASE),
]

MEDIUM_SIGNAL_PATTERNS: list[re.Pattern] = [
    re.compile(r"\blaunch\b", re.IGNORECASE),
    re.compile(r"\blançamento\b", re.IGNORECASE),
    re.compile(r"\bnew product\b", re.IGNORECASE),
    re.compile(r"\bpartnership\b", re.IGNORECASE),
    re.compile(r"\bparceria\b", re.IGNORECASE),
    re.compile(r"\bhiring\b", re.IGNORECASE),
    re.compile(r"\bnova vaga\b", re.IGNORECASE),
]


class ChangeDetector:
    """Detect meaningful changes between scraping runs for a URL."""

    def detect(
        self,
        old_hash: str,
        new_hash: str,
        old_text: str,
        new_text: str,
    ) -> ChangeReport:
        """Compare two scraping runs and report changes.

        Args:
            old_hash: SHA-256 hash of the previous ``extracted_text``.
            new_hash: SHA-256 hash of the current ``extracted_text``.
            old_text: Previously extracted clean text.
            new_text: Currently extracted clean text.

        Returns:
            ChangeReport with detected changes and significance.
        """
        if old_hash == new_hash:
            return ChangeReport(changed=False)

        sections = self._diff_sections(old_text, new_text)
        significance = self._rate_significance(new_text, sections)
        return ChangeReport(
            changed=True,
            sections_changed=sections,
            significance=significance,
        )

    @staticmethod
    def _diff_sections(old_text: str, new_text: str) -> list[SectionChange]:
        """Line-based diff using difflib to identify actual changes."""
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()

        diff = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile="old", tofile="new",
            n=3,  # context lines
        ))

        added_lines: list[str] = []
        removed_lines: list[str] = []
        for line in diff:
            # Skip unified diff headers (---/+++/@@)
            if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
                continue
            if line.startswith("+"):
                added_lines.append(line[1:])
            elif line.startswith("-"):
                removed_lines.append(line[1:])

        changes: list[SectionChange] = []
        if added_lines:
            added_text = "\n".join(added_lines[:20])
            changes.append(SectionChange(old_text="", new_text=added_text, section_type="added"))
        if removed_lines:
            removed_text = "\n".join(removed_lines[:20])
            changes.append(SectionChange(old_text=removed_text, new_text="", section_type="removed"))
        return changes

    @staticmethod
    def _rate_significance(new_text: str, sections: list[SectionChange]) -> Significance:
        """Rate the significance of detected changes.

        Looks for high-value signals (funding, acquisition, etc.) in
        the new text and changed sections.
        """
        combined = new_text
        for s in sections:
            combined += "\n" + s.new_text

        for pattern in CRITICAL_SIGNAL_PATTERNS:
            if pattern.search(combined):
                return Significance.CRITICAL

        for pattern in HIGH_SIGNAL_PATTERNS:
            if pattern.search(combined):
                return Significance.HIGH

        for pattern in MEDIUM_SIGNAL_PATTERNS:
            if pattern.search(combined):
                return Significance.MEDIUM

        return Significance.LOW
