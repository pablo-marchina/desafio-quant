"""Source classification and allowlist helpers for public startup research."""

from urllib.parse import urlparse

from src.extraction.schemas import SourceType
from src.quantitative.params import SOURCE_QUALITY_SCORES

_KNOWN_OFFICIAL_HINTS = ("about", "company", "careers", "blog")


def source_quality_score(source_type: SourceType) -> float:
    return SOURCE_QUALITY_SCORES.get(source_type.value, 0.3)


def classify_source(url: str) -> SourceType:
    """Classify a public source using simple URL-based heuristics."""

    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    if "linkedin.com" in host:
        return SourceType.FOUNDER_PROFILE
    if any(news_host in host for news_host in ("exame.com", "valor.globo.com", "neofeed.com.br")):
        return SourceType.NEWS
    if "jobs" in host or "careers" in path:
        return SourceType.JOB_POST
    if "blog" in host or "blog" in path:
        return SourceType.BLOG
    if any(hint in path for hint in _KNOWN_OFFICIAL_HINTS):
        return SourceType.OFFICIAL_SITE
    return SourceType.OFFICIAL_SITE  # default fallback for known startup domains



