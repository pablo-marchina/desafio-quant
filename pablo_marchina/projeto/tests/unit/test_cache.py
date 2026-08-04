"""Unit tests for src.scraping.cache."""

import hashlib
from datetime import timedelta
from unittest.mock import patch

import pytest

from src.scraping.cache import (
    _normalize_url,
    _url_key,
    _FRESHNESS_TTL,
    _FRESHNESS_POLICY_MAP,
    reset_cache,
    scrape_cache,
)


@pytest.fixture(autouse=True)
def reset_cache_state():
    reset_cache()
    yield
    reset_cache()


def test_get_set_roundtrip():
    url = "https://example.com/page"
    content = "<html>test</html>"
    with scrape_cache() as cache:
        cache.set(url, content)
        cached = cache.get(url)
    assert cached == content


def test_get_returns_none_for_missing():
    with scrape_cache() as cache:
        cached = cache.get("https://example.com/nonexistent")
    assert cached is None


def test_set_with_etag_last_modified():
    url = "https://example.com/page"
    content = "<html>etag-test</html>"
    with scrape_cache() as cache:
        cache.set(url, content, etag='"abc123"', last_modified="Mon, 01 Jan 2024 00:00:00 GMT")
        _, meta = cache.get_with_meta(url)
    assert meta.get("etag") == '"abc123"'
    assert meta.get("last_modified") == "Mon, 01 Jan 2024 00:00:00 GMT"


def test_invalidate_removes_entry():
    url = "https://example.com/page"
    with scrape_cache() as cache:
        cache.set(url, "content")
        cache.invalidate(url)
        cached = cache.get(url)
    assert cached is None


def test_hash_history_roundtrip():
    url = "https://example.com/page"
    hash_val = "abcdef1234567890"
    with scrape_cache() as cache:
        cache.record_hash(url, hash_val)
        history = cache.get_hash_history(url)
    assert hash_val in history


def test_hash_history_max_entries():
    url = "https://example.com/page"
    with scrape_cache() as cache:
        for i in range(15):
            cache.record_hash(url, f"hash_{i}", max_entries=10)
        history = cache.get_hash_history(url, max_entries=10)
    assert len(history) == 10


def test_clear():
    url = "https://example.com/page"
    with scrape_cache() as cache:
        cache.set(url, "content")
        cache.clear()
        cached = cache.get(url)
    assert cached is None


def test_stats():
    with scrape_cache() as cache:
        stats = cache.stats()
    assert "size" in stats
    assert "count" in stats
    assert "directory" in stats


def test_normalize_url_case_insensitive():
    url1 = "https://Example.COM/Path"
    url2 = "https://example.com/path"
    key1 = _url_key(url1)
    key2 = _url_key(url2)
    assert key1 == key2


def test_normalize_url_trailing_slash():
    url1 = "https://example.com/page/"
    url2 = "https://example.com/page"
    key1 = _url_key(url1)
    key2 = _url_key(url2)
    assert key1 == key2


def test_ttl_by_policy_direct_match():
    """Keys in _FRESHNESS_TTL should resolve directly."""
    assert "daily" in _FRESHNESS_TTL
    assert isinstance(_FRESHNESS_TTL["daily"], timedelta)
    assert _FRESHNESS_TTL["daily"].total_seconds() == 86400


def test_ttl_by_policy_mapped():
    """Rate-limit policy IDs should map to freshness TTLs."""
    assert "news_site" in _FRESHNESS_POLICY_MAP
    mapped = _FRESHNESS_POLICY_MAP["news_site"]
    assert mapped in _FRESHNESS_TTL


def test_ttl_default_when_unknown():
    """Unknown policies should fall back to 24h default."""
    url = "https://example.com/page"
    content = "test"
    with scrape_cache() as cache:
        cache.set(url, content, policy="nonexistent_policy_xyz")
        cached = cache.get(url)
    assert cached == content
