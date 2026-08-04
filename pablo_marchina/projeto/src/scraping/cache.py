"""Disk-backed LRU cache with TTL per freshness policy and conditional HTTP support.

Wraps ``diskcache.Cache`` with typed helpers for scraping results.
Each entry is keyed by URL (normalized) and tagged with a freshness policy
that determines its TTL.

Usage:

    from src.scraping.cache import scrape_cache

    with scrape_cache() as cache:
        cached = cache.get("https://example.com/doc")
        if cached is None:
            raw = fetch_page("https://example.com/doc")
            cache.set("https://example.com/doc", raw.text, policy="default_polite")
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import diskcache
except ImportError:  # pragma: no cover - fallback for minimal clean environments
    class _MemoryCache:
        def __init__(self, *args, **kwargs):
            self._data = {}

        def get(self, key):
            return self._data.get(key)

        def set(self, key, value, expire=None):
            self._data[key] = value

        def delete(self, key):
            self._data.pop(key, None)

        def clear(self):
            self._data.clear()

        def volume(self):
            return sum(len(str(v)) for v in self._data.values())

        def close(self):
            pass

        def __len__(self):
            return len(self._data)

    class diskcache:  # type: ignore[no-redef]
        Cache = _MemoryCache

from src.scraping.rate_limit_policy import list_policies_requiring_api_key

logger = logging.getLogger(__name__)

_PRODUCT_DATA_DIR = Path(os.getenv("PRODUCT_DATA_DIR", "data/product"))
_CACHE_DIR = Path(os.getenv("SCRAPING_CACHE_DIR", str(_PRODUCT_DATA_DIR / "scraping-cache")))
_DEFAULT_SIZE_LIMIT = 2**30  # 1 GiB

_FRESHNESS_TTL: dict[str, timedelta] = {
    "daily": timedelta(hours=24),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
    "static": timedelta(days=365),
}

# Map from rate-limit policy IDs / source types to freshness categories.
# Used by ``set()`` to determine the appropriate TTL when a policy string
# is passed instead of a freshness key.
_FRESHNESS_POLICY_MAP: dict[str, str] = {
    "news": "daily",
    "news_site": "daily",
    "rss": "daily",
    "blog": "weekly",
    "directory": "weekly",
    "directory_listing": "weekly",
    "default_polite": "weekly",
    "official": "monthly",
    "nvidia": "monthly",
    "nvidia_eco": "monthly",
    "static": "static",
    "github": "weekly",
    "github_api": "weekly",
    "search_engine": "daily",
}

_SCRAPE_CACHE: diskcache.Cache | None = None


def _get_cache() -> diskcache.Cache:
    global _SCRAPE_CACHE
    if _SCRAPE_CACHE is None:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _SCRAPE_CACHE = diskcache.Cache(
            directory=str(_CACHE_DIR),
            size_limit=_DEFAULT_SIZE_LIMIT,
            eviction_policy="least-recently-used",
        )
    return _SCRAPE_CACHE


def reset_cache() -> None:
    global _SCRAPE_CACHE
    if _SCRAPE_CACHE is not None:
        _SCRAPE_CACHE.close()
        _SCRAPE_CACHE = None


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc.lower()}{parsed.path.lower().rstrip('/') or '/'}"


def _url_key(url: str) -> str:
    return hashlib.sha256(_normalize_url(url).encode()).hexdigest()


_CachedValue = tuple[str, dict[str, Any]]  # (html, metadata)
_METADATA_KEY = "_meta"


@contextlib.contextmanager
def scrape_cache():
    """Context manager yielding the global scraping cache.

    Usage::

        with scrape_cache() as cache:
            cached = cache.get(url)
            if cached:
                return cached
            ...
            cache.set(url, value)
    """
    c = _get_cache()
    try:
        yield _ScopedCache(c)
    finally:
        pass  # keep alive for reuse; call reset_cache() to close


class _ScopedCache:
    """Thin typed wrapper over ``diskcache.Cache`` for scraping artifacts."""

    def __init__(self, cache: diskcache.Cache) -> None:
        self._cache = cache

    def get(self, url: str) -> str | None:
        key = _url_key(url)
        raw = self._cache.get(key)
        if raw is not None:
            logger.debug("CACHE HIT  %s", url)
        return raw

    def get_with_meta(self, url: str) -> tuple[str | None, dict[str, Any]]:
        """Return ``(html, metadata)`` where metadata includes etag/last_modified."""
        key = _url_key(url)
        raw = self._cache.get(key)
        meta: dict[str, Any] = {}
        if raw is not None:
            meta_key = f"{key}{_METADATA_KEY}"
            meta_raw = self._cache.get(meta_key)
            if isinstance(meta_raw, dict):
                meta = meta_raw
            logger.debug("CACHE HIT (meta) %s", url)
        return (raw, meta)

    def set(
        self,
        url: str,
        text: str,
        policy: str = "default_polite",
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> None:
        key = _url_key(url)
        # Try exact match, then partial match via _FRESHNESS_POLICY_MAP, then default 24h
        ttl = _FRESHNESS_TTL.get(policy)
        if ttl is None:
            mapped_key = _FRESHNESS_POLICY_MAP.get(policy)
            if mapped_key:
                ttl = _FRESHNESS_TTL.get(mapped_key)
        if ttl is None:
            ttl = timedelta(hours=24)
        self._cache.set(key, text, expire=ttl.total_seconds())
        # Store metadata separately
        meta: dict[str, Any] = {}
        if etag:
            meta["etag"] = etag
        if last_modified:
            meta["last_modified"] = last_modified
        if meta:
            meta_key = f"{key}{_METADATA_KEY}"
            self._cache.set(meta_key, meta, expire=ttl.total_seconds())
        logger.debug("CACHE SET  %s  ttl=%s", url, ttl)

    def invalidate(self, url: str) -> None:
        key = _url_key(url)
        self._cache.delete(key)
        self._cache.delete(f"{key}{_METADATA_KEY}")
        logger.debug("CACHE DEL  %s", url)

    def get_hash_history(self, url: str, max_entries: int = 10) -> list[str]:
        """Return list of past content hashes for *url*, newest first."""
        key = _url_key(url)
        history_key = f"{key}_hash_history"
        history: list[str] = self._cache.get(history_key) or []
        return history[:max_entries]

    def record_hash(self, url: str, hash_value: str, max_entries: int = 10) -> None:
        """Store *hash_value* in the hash history for *url*, keep last *max_entries*."""
        key = _url_key(url)
        history_key = f"{key}_hash_history"
        history: list[str] = self._cache.get(history_key) or []
        if hash_value in history:
            history.remove(hash_value)
        history.insert(0, hash_value)
        self._cache.set(history_key, history[:max_entries], expire=None)

    def clear(self) -> None:
        self._cache.clear()
        logger.info("CACHE cleared")

    def stats(self) -> dict[str, Any]:
        return {
            "size": self._cache.volume(),
            "size_limit": _DEFAULT_SIZE_LIMIT,
            "count": len(self._cache),
            "directory": str(_CACHE_DIR),
        }
