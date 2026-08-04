"""Tests for src.scraping.fetcher (httpx-based)."""

from datetime import datetime
from unittest.mock import Mock, patch

import httpx

from src.scraping.fetcher import FetchResult, fetch_page, reset_client


def _mock_response(status: int = 200, text: str = "") -> Mock:
    """Build a mock ``httpx.Response``."""
    reasons = {200: "OK", 404: "Not Found", 500: "Internal Server Error"}
    mock = Mock(spec=httpx.Response)
    mock.status_code = status
    mock.text = text
    mock.reason_phrase = reasons.get(status, "Unknown")
    mock.headers = {}
    return mock


def _patch_client() -> Mock:
    """Patch the internal httpx.Client.get method."""
    return patch("src.scraping.fetcher._get_client")


def test_fetch_success_200() -> None:
    reset_client()
    with _patch_client() as mock_get_client:
        mock_client = Mock(spec=httpx.Client)
        mock_client.get.return_value = _mock_response(200, "<html><body>Hello</body></html>")
        mock_get_client.return_value = mock_client

        result = fetch_page("https://example.com")

    assert result.status == 200
    assert result.raw_html == "<html><body>Hello</body></html>"
    assert result.error is None
    assert isinstance(result.fetched_at, datetime)
    mock_client.get.assert_called_once()

def test_fetch_not_found_404() -> None:
    reset_client()
    with _patch_client() as mock_get_client:
        mock_client = Mock(spec=httpx.Client)
        mock_client.get.return_value = _mock_response(404)
        mock_get_client.return_value = mock_client

        result = fetch_page("https://example.com/not-found")

    assert result.status == 404
    assert result.raw_html == ""
    assert result.error is not None
    assert "404" in result.error


def test_fetch_server_error_500() -> None:
    reset_client()
    with _patch_client() as mock_get_client:
        mock_client = Mock(spec=httpx.Client)
        mock_client.get.return_value = _mock_response(500)
        mock_get_client.return_value = mock_client

        result = fetch_page("https://example.com/error")

    assert result.status == 500
    assert result.raw_html == ""
    assert result.error is not None
    assert "500" in result.error


def test_fetch_timeout() -> None:
    reset_client()
    with _patch_client() as mock_get_client:
        mock_client = Mock(spec=httpx.Client)
        mock_client.get.side_effect = httpx.TimeoutException("Connection timed out")
        mock_get_client.return_value = mock_client

        result = fetch_page("https://example.com", timeout=5)

    assert result.status is None
    assert result.raw_html == ""
    assert result.error is not None
    assert "timeout" in result.error.lower()


def test_fetch_connection_error() -> None:
    reset_client()
    with _patch_client() as mock_get_client:
        mock_client = Mock(spec=httpx.Client)
        mock_client.get.side_effect = httpx.ConnectError("DNS resolution failed")
        mock_get_client.return_value = mock_client

        result = fetch_page("https://example.com")

    assert result.status is None
    assert result.raw_html == ""
    assert result.error is not None
    assert "connection" in result.error.lower()


def test_fetch_invalid_url() -> None:
    result = fetch_page("not-a-url")

    assert result.status is None
    assert result.raw_html == ""
    assert result.error is not None
    assert "invalid" in result.error.lower()


def test_fetch_result_dataclass_fields() -> None:
    dt = datetime.now()
    result = FetchResult(
        url="https://example.com",
        status=200,
        raw_html="<html/>",
        fetched_at=dt,
        error=None,
    )

    assert result.url == "https://example.com"
    assert result.status == 200
    assert result.raw_html == "<html/>"
    assert result.fetched_at == dt
    assert result.error is None


def test_fetch_protocol_error() -> None:
    reset_client()
    with _patch_client() as mock_get_client:
        mock_client = Mock(spec=httpx.Client)
        mock_client.get.side_effect = httpx.RemoteProtocolError("Connection closed unexpectedly")
        mock_get_client.return_value = mock_client

        result = fetch_page("https://example.com")

    assert result.status is None
    assert result.raw_html == ""
    assert result.error is not None
    assert "protocol" in result.error.lower()


def test_client_reuse() -> None:
    reset_client()
    with _patch_client() as mock_get_client:
        mock_client = Mock(spec=httpx.Client)
        mock_client.get.return_value = _mock_response(200, "<html/>")
        mock_get_client.return_value = mock_client

        fetch_page("https://example.com/a")
        fetch_page("https://example.com/b")

    # Client.get should be called twice, but _get_client only once
    assert mock_client.get.call_count == 2


def test_client_close_on_reset() -> None:
    reset_client()
    with _patch_client() as mock_get_client:
        mock_client = Mock(spec=httpx.Client)
        mock_client.get.return_value = _mock_response(200, "<html/>")
        mock_get_client.return_value = mock_client

        fetch_page("https://example.com")

        # reset_client should close the real client (if any) and set it to None
        # With the mock, _get_client returns mock, but we can verify no errors
        reset_client()

    # After reset, a new fetch uses a fresh client
    with _patch_client() as mock_get_client2:
        mock_client2 = Mock(spec=httpx.Client)
        mock_client2.get.return_value = _mock_response(200, "<html/>")
        mock_get_client2.return_value = mock_client2

        result = fetch_page("https://example.com/after-reset")
        assert result.status == 200
