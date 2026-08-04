"""Reddit-based startup discovery using PRAW.

Requires ``REDDIT_CLIENT_ID``, ``REDDIT_CLIENT_SECRET``, ``REDDIT_USER_AGENT``
environment variables.  Degrades gracefully (logs warning) when unset.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SUBREDDITS = ["startups", "artificial", "MachineLearning", "brdev", "brasil"]
SEARCH_QUERIES = ["AI startup", "Brazilian startup", "ML startup", "funding", "seed round"]


class RedditCollector:
    """Collect startup mentions from Reddit subreddits.

    Uses PRAW to search configured subreddits for AI startup related
    posts.  Returns results matching the same SearchResult interface
    used by the rest of the discovery pipeline.
    """

    def __init__(self) -> None:
        self._ready = False
        self._reddit = None
        client_id = os.environ.get("REDDIT_CLIENT_ID")
        client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
        user_agent = os.environ.get("REDDIT_USER_AGENT", "NVIDIAStartupAIRadar/0.1")
        if client_id and client_secret:
            try:
                import praw
                self._reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent,
                )
                self._ready = True
            except Exception as exc:
                logger.warning("RedditCollector init failed: %s", exc)
        else:
            logger.info("RedditCollector: REDDIT_CLIENT_ID/SECRET not set — disabled")

    def search(self, query: str = "", max_results: int = 20) -> list[dict[str, Any]]:
        """Search Reddit for *query* across default subreddits.

        Args:
            query:  Search term (defaults to the configured list).
            max_results:  Max posts per subreddit.

        Returns:
            List of result dicts with keys ``url``, ``title``, ``snippet``, ``source_engine``.
        """
        if not self._ready:
            return []

        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        subreddits = os.environ.get("REDDIT_SUBREDDITS", ",".join(DEFAULT_SUBREDDITS)).split(",")
        queries = [query] if query else SEARCH_QUERIES

        for sub_name in subreddits:
            sub_name = sub_name.strip()
            if not sub_name:
                continue
            try:
                sub = self._reddit.subreddit(sub_name)
                for q in queries:
                    for post in sub.search(q, limit=max_results):
                        url = f"https://reddit.com{post.permalink}"
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        results.append({
                            "url": url,
                            "title": post.title,
                            "snippet": post.selftext[:300] if post.selftext else "",
                            "source_engine": f"reddit/{sub_name}",
                        })
            except Exception as exc:
                logger.debug("RedditCollector: error in r/%s: %s", sub_name, exc)

        return results
