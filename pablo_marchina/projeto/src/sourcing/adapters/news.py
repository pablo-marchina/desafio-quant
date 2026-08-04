from __future__ import annotations

import re
from urllib.parse import urlparse

from src.sourcing.adapters.base import SourceResult
from src.sourcing.adapters.static_html import StaticHtmlAdapter

KNOWN_NEWS_DOMAINS: set[str] = {
    "braziljournal.com",
    "neofeed.com.br",
    "exame.com",
    "startups.com.br",
    "revistapegn.globo.com",
    "valor.globo.com",
    "meioemensagem.com.br",
    "mobiletime.com.br",
    "startse.com",
    "distrito.me",
}


def _is_news_url(url: str) -> bool:
    """Heuristic check: does *url* look like a news article?"""
    parsed = urlparse(url)
    domain = parsed.netloc.lower().removeprefix("www.")
    if domain in KNOWN_NEWS_DOMAINS:
        return True
    # Generic article-path heuristic
    path = parsed.path.lower()
    return bool(re.search(r"/(news|noticia|artigo|post|blog|materia|conteudo)/", path))


def _extract_article_title(html: str) -> str | None:
    """Try to extract article title from HTML meta tags or h1."""
    import re as _re

    # Open Graph title
    m = _re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html, _re.IGNORECASE)
    if m:
        return m.group(1)
    # Twitter title
    m = _re.search(r'<meta\s+name="twitter:title"\s+content="([^"]+)"', html, _re.IGNORECASE)
    if m:
        return m.group(1)
    # <h1> tag
    m = _re.search(r"<h1[^>]*>([^<]+)</h1>", html, _re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


class NewsAdapter(StaticHtmlAdapter):
    """Collect news articles from trusted media sources.

    Validates that the target URL looks like a news article and extracts
    headline metadata (og:title, h1) as structured evidence.
    """

    source_type = "trusted_news"

    def collect(self, target: str) -> SourceResult:
        if not _is_news_url(target):
            return SourceResult(
                target=target,
                status="skipped",
                raw_text="",
                error="URL does not appear to be a news article",
            )

        base_result = super().collect(target)
        if base_result.status != "collected":
            return base_result

        title = _extract_article_title(base_result.raw_text)
        if title:
            from src.sourcing.adapters.base import EvidenceSpan

            extra = EvidenceSpan(text=f"Article title: {title}", source_url=target, confidence=0.7)
            return SourceResult(
                target=base_result.target,
                status=base_result.status,
                raw_text=base_result.raw_text,
                evidence_spans=base_result.evidence_spans + [extra],
                content_hash=base_result.content_hash,
            )
        return SourceResult(
            target=base_result.target,
            status=base_result.status,
            raw_text=base_result.raw_text,
            evidence_spans=base_result.evidence_spans,
            content_hash=base_result.content_hash,
        )
