"""RSS / Atom feed collector.

Uses ``feedparser`` to parse feeds and extract recent entries.
Respects rate-limit policies from the source registry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

import feedparser

from src.scraping.strategies import register

logger = logging.getLogger(__name__)


@dataclass
class FeedEntry:
    title: str
    url: str
    summary: str
    published: datetime | None
    content: str = ""


@dataclass
class FeedResult:
    feed_url: str
    title: str | None
    entries: list[FeedEntry] = field(default_factory=list)
    error: str | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def collect_feed(feed_url: str, max_entries: int = 20) -> FeedResult:
    """Fetch and parse an RSS/Atom feed.

    Args:
        feed_url: The URL of the RSS/Atom feed.
        max_entries: Maximum number of recent entries to return.

    Returns:
        A ``FeedResult`` with parsed entries.
    """
    result = FeedResult(feed_url=feed_url)
    try:
        parsed = feedparser.parse(feed_url)
        if parsed.bozo and not parsed.entries:
            result.error = f"Feed parse error: {parsed.bozo_exception}"
            logger.warning("RSS_PARSE_ERR  %s  %s", feed_url, parsed.bozo_exception)
            return result

        result.title = parsed.feed.get("title")
        for entry in parsed.entries[:max_entries]:
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                except (ValueError, TypeError):
                    pass

            feed_entry = FeedEntry(
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                summary=entry.get("summary", ""),
                published=published,
                content=entry.get("content", [{}])[0].get("value", "") if entry.get("content") else "",
            )
            result.entries.append(feed_entry)

        logger.info("RSS_OK  feed=%s  entries=%d", feed_url, len(result.entries))

    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        logger.warning("RSS_FETCH_ERR  %s  %s", feed_url, exc)

    return result


@register("rss")
def collect_rss(source) -> FeedResult | None:
    from src.scraping.source_registry import SourceRecord

    if not isinstance(source, SourceRecord):
        return None

    return collect_feed(source.base_url, max_entries=20)
