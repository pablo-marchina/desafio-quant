"""Hacker News discovery via the official Firebase API.

No API key required — entirely free and rate-limited at ~1 req/s.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
HN_ITEM_URL = f"{HN_API_BASE}/item"
_TOP_STORIES_CACHE_SIZE = 50


class HackerNewsCollector:
    """Collect startup-relevant posts from Hacker News.

    Fetches top/new stories and filters by AI/startup keywords.
    """

    def __init__(self) -> None:
        self._client = httpx.Client(timeout=15.0)
        self._top_stories: list[int] = []

    def search(self, query: str = "", max_results: int = 30) -> list[dict[str, Any]]:
        """Search Hacker News for AI/startup related posts.

        Args:
            query:  Optional keyword filter (case-insensitive substring match).
            max_results:  Max stories to scan.

        Returns:
            List of result dicts with keys ``url``, ``title``, ``snippet``, ``source_engine``.
        """
        results: list[dict[str, Any]] = []
        seen_ids: set[int] = set()

        story_ids = self._fetch_story_ids("topstories", count=max_results * 2)

        for sid in story_ids[: max_results * 3]:
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            try:
                item_url = f"{HN_ITEM_URL}/{sid}.json"
                resp = self._client.get(item_url, timeout=10.0)
                if resp.status_code != 200:
                    continue
                item = resp.json()
                if not item or item.get("type") != "story" or item.get("title") is None:
                    continue
                title: str = item["title"]
                url: str = item.get("url", f"https://news.ycombinator.com/item?id={sid}")
                text: str = item.get("text", "")

                if query and query.lower() not in title.lower() and query.lower() not in text.lower():
                    continue

                results.append({
                    "url": url,
                    "title": title,
                    "snippet": text[:300] if text else title,
                    "source_engine": "hackernews",
                })

                if len(results) >= max_results:
                    break
            except Exception as exc:
                logger.debug("HackerNewsCollector: failed to fetch item %d: %s", sid, exc)

        return results

    def _fetch_story_ids(self, endpoint: str, count: int = 30) -> list[int]:
        """Fetch story IDs from the HN API."""
        try:
            resp = self._client.get(f"{HN_API_BASE}/{endpoint}.json", timeout=10.0)
            if resp.status_code == 200:
                return (resp.json() or [])[:count]
        except Exception as exc:
            logger.debug("HackerNewsCollector: failed to fetch %s: %s", endpoint, exc)
        return []

    def close(self) -> None:
        self._client.close()
