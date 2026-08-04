from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

try:
    from langdetect import detect as lang_detect
    from langdetect.lang_detect_exception import LangDetectException
except ImportError:
    lang_detect = None
    # Stub exception that can only be raised by our code, not by arbitrary bugs
    class LangDetectException(Exception):
        pass

import src.scraping.tech_stack_detector as tsd

logger = logging.getLogger(__name__)


class QualityIssue(str, Enum):
    TOO_SHORT = "too_short"
    BOILERPLATE = "boilerplate"
    LOGIN_WALL = "login_wall"
    NOT_FOUND = "not_found"
    ACCESS_DENIED = "access_denied"
    CAPTCHA = "captcha"
    JS_REQUIRED = "js_required"
    PAYWALL = "paywall"
    CLOUDFLARE = "cloudflare"
    UNEXPECTED_LANGUAGE = "unexpected_language"


BOILERPLATE_PATTERNS: list[re.Pattern] = [
    re.compile(r"Access Denied", re.IGNORECASE),
    re.compile(r"Please enable JavaScript", re.IGNORECASE),
    re.compile(r"Enter the characters you see below", re.IGNORECASE),
    re.compile(r"Your request has been blocked", re.IGNORECASE),
    re.compile(r"Sorry, you have been blocked", re.IGNORECASE),
    re.compile(r"Página não encontrada", re.IGNORECASE),
    re.compile(r"404 Not Found", re.IGNORECASE),
    re.compile(r"Just a moment\.\.\.", re.IGNORECASE),
    re.compile(r"Checking your browser", re.IGNORECASE),
    re.compile(r"Verificando o navegador", re.IGNORECASE),
    re.compile(r"DDoS protection", re.IGNORECASE),
    re.compile(r"This page is blocked", re.IGNORECASE),
    re.compile(r"Esta página foi bloqueada", re.IGNORECASE),
]

LOGIN_SIGNALS: list[str] = [
    "login",
    "sign in",
    "entrar",
    "log in",
    "authentication",
    "autenticação",
    "faça login",
    "conecte-se",
]

PAYWALL_SIGNALS: list[str] = [
    "subscribe",
    "assinatura",
    "assine",
    "inscreva-se",
    "premium",
    "acesso liberado",
    "continue reading",
    "continue lendo",
    "apenas para assinantes",
]


class ContentQuality:
    """Result of a content quality check."""

    def __init__(
        self,
        is_valid: bool,
        issues: list[QualityIssue] | None = None,
        content_length: int = 0,
        error: str | None = None,
    ):
        self.is_valid = is_valid
        self.issues = issues or []
        self.content_length = content_length
        self.error = error

    def __repr__(self) -> str:
        return f"ContentQuality(valid={self.is_valid}, issues={self.issues})"


class ContentQualityValidator:
    """Validate scraped HTML/text content quality before extraction."""

    MIN_CONTENT_LENGTH = 200

    def validate(self, html_or_text: str, url: str = "") -> ContentQuality:
        """Return quality assessment with detected issues.

        Args:
            html_or_text: Raw HTML or extracted text.
            url: Source URL (used for domain-level heuristics).

        Returns:
            ContentQuality with validation result.
        """
        issues: list[QualityIssue] = []
        text = html_or_text

        # Empty / too short
        if not text or len(text.strip()) < self.MIN_CONTENT_LENGTH:
            issues.append(QualityIssue.TOO_SHORT)

        # Boilerplate / error pages
        for pattern in BOILERPLATE_PATTERNS:
            if pattern.search(text):
                issues.append(QualityIssue.BOILERPLATE)
                break

        # Login walls
        login_count = sum(1 for s in LOGIN_SIGNALS if s in text.lower())
        if login_count >= 3:
            issues.append(QualityIssue.LOGIN_WALL)

        # Paywall
        paywall_count = sum(1 for s in PAYWALL_SIGNALS if s in text.lower())
        if paywall_count >= 2:
            issues.append(QualityIssue.PAYWALL)

        # Cloudflare
        if "cloudflare" in text.lower() or "cf-ray" in text.lower():
            issues.append(QualityIssue.CLOUDFLARE)

        # Language detection — flag if not Portuguese or English (BR-focused project)
        if lang_detect is not None and len(text.strip()) > 100:
            try:
                detected = lang_detect(text[:2000])
                if detected not in ("pt", "en"):
                    issues.append(QualityIssue.UNEXPECTED_LANGUAGE)
            except LangDetectException:
                logger.debug("Language detection failed for %s", url)

        return ContentQuality(
            is_valid=len(issues) == 0,
            issues=issues,
            content_length=len(text),
        )
