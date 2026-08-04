"""Unit tests for src.scraping.circuit_breaker."""

import time
from unittest.mock import patch

import pytest

from src.scraping.circuit_breaker import CircuitBreaker


@pytest.fixture
def cb():
    return CircuitBreaker(failure_threshold=3, recovery_timeout=1)


def test_initially_closed(cb):
    assert cb.is_open("https://example.com") is False


def test_opens_after_threshold_failures(cb):
    url = "https://example.com"
    for _ in range(2):
        cb.record_failure(url)
        assert cb.is_open(url) is False
    cb.record_failure(url)
    assert cb.is_open(url) is True


def test_records_success_resets_failures(cb):
    url = "https://example.com"
    for _ in range(3):
        cb.record_failure(url)
    assert cb.is_open(url) is True
    cb.record_success(url)
    assert cb.is_open(url) is False


def test_half_open_transition_after_timeout(cb):
    url = "https://example.com"
    for _ in range(3):
        cb.record_failure(url)
    assert cb.is_open(url) is True

    # Wait for recovery timeout
    time.sleep(1.1)

    assert cb.is_open(url) is False  # now half-open


def test_probe_allowed_in_half_open(cb):
    url = "https://example.com"
    for _ in range(3):
        cb.record_failure(url)
    time.sleep(1.1)

    # Should be half-open now: is_open returns False (probe allowed)
    assert cb.is_open(url) is False


def test_probe_success_closes_circuit(cb):
    url = "https://example.com"
    for _ in range(3):
        cb.record_failure(url)
    time.sleep(1.1)

    cb.is_open(url)  # triggers half-open transition
    cb.record_success(url)
    assert cb.is_open(url) is False


def test_different_domains_independent(cb):
    url_a = "https://site-a.com"
    url_b = "https://site-b.com"
    for _ in range(3):
        cb.record_failure(url_a)

    assert cb.is_open(url_a) is True
    assert cb.is_open(url_b) is False


def test_reset(cb):
    url = "https://example.com"
    for _ in range(3):
        cb.record_failure(url)
    assert cb.is_open(url) is True
    cb.reset()
    assert cb.is_open(url) is False


def test_record_failure_increments_counter(cb):
    url = "https://example.com"
    cb.record_failure(url)
    cb.record_failure(url)
    # Not open yet (threshold = 3)
    assert cb.is_open(url) is False
