"""Unit tests for src.scraping.fuzzy_dedup."""

import pytest

from src.scraping.fuzzy_dedup import FuzzyIndex, exact_dedup, content_hash


class TestExactDedup:
    def test_detects_duplicate(self):
        seen = set()
        assert exact_dedup(seen, "Hello World") is False
        assert exact_dedup(seen, "Hello World") is True

    def test_unique_texts(self):
        seen = set()
        assert exact_dedup(seen, "Hello") is False
        assert exact_dedup(seen, "World") is False


class TestFuzzyIndex:
    def test_similar_detected(self):
        index = FuzzyIndex(threshold=0.8)
        index.index("NVIDIA is a great company for AI startups")
        assert index.is_duplicate("NVIDIA is a great company for AI") is True

    def test_different_not_detected(self):
        index = FuzzyIndex(threshold=0.9)
        index.index("NVIDIA is a great company for AI startups")
        assert index.is_duplicate("Apple makes iPhones and laptops") is False

    def test_clear(self):
        index = FuzzyIndex(threshold=0.8)
        index.index("Hello World")
        index.clear()
        assert index.is_duplicate("Hello World") is False

    def test_threshold_configurable(self):
        index = FuzzyIndex(threshold=0.99)
        index.index("NVIDIA is a great company for AI startups")
        assert index.is_duplicate("NVIDIA is a great company for machine learning") is False

    def test_empty_text(self):
        index = FuzzyIndex(threshold=0.8)
        assert index.is_duplicate("") is False


class TestContentHash:
    def test_consistent_for_same_input(self):
        text = "Hello World"
        h1 = content_hash(text)
        h2 = content_hash(text)
        assert h1 == h2

    def test_different_for_different_input(self):
        h1 = content_hash("Hello")
        h2 = content_hash("World")
        assert h1 != h2

    def test_strips_whitespace(self):
        h1 = content_hash("  Hello World  ")
        h2 = content_hash("Hello World")
        assert h1 == h2

    def test_case_insensitive(self):
        h1 = content_hash("Hello World")
        h2 = content_hash("hello world")
        assert h1 == h2

    def test_empty_string(self):
        h = content_hash("")
        assert isinstance(h, str)
        assert len(h) > 0
