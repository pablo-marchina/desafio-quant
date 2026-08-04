"""HTTP fetching for single public URL collection.

Migrated from ``requests`` to ``httpx`` for HTTP/2, connection pooling,
and granular timeout support.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

try:
    from fake_useragent import UserAgent
except ImportError:
    UserAgent = None  # type: ignore[assignment,misc]

try:
    _ua = UserAgent(browsers=["chrome", "firefox", "edge"]) if UserAgent is not None else None
except Exception:
    _ua = None

_DEFAULT_TIMEOUT = 15
_DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB

_client: httpx.Client | None = None
_client_no_redirect: httpx.Client | None = None


def _random_ua() -> str:
    if _ua is not None:
        try:
            return _ua.random
        except Exception:
            pass
    return "Mozilla/5.0 (compatible; NVIDIAStartupAIRadar/0.1; +https://github.com/nvidia/startup-ai-radar)"


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
        _client = httpx.Client(
            http2=True,
            timeout=httpx.Timeout(_DEFAULT_TIMEOUT, connect=10.0),
            headers={"User-Agent": _random_ua()},
            follow_redirects=True,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
            ),
            proxy=proxy,
        )
    return _client


def _build_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"User-Agent": _random_ua()}
    if extra:
        headers.update(extra)
    return headers


def reset_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


@dataclass(slots=True)
class FetchResult:
    url: str
    status: int | None
    raw_html: str
    fetched_at: datetime
    error: str | None
    raw_headers: dict[str, str] | None = None
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False
    content_type_warning: bool = False


def fetch_page(
    url: str,
    timeout: int = _DEFAULT_TIMEOUT,
    *,
    if_none_match: str | None = None,
    if_modified_since: str | None = None,
) -> FetchResult:
    """Fetch a single public URL with optional conditional HTTP caching.

    When *if_none_match* or *if_modified_since* are provided, the server
    may return ``304 Not Modified``.  In that case ``not_modified`` is
    set to ``True`` and ``raw_html`` is empty.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return FetchResult(
            url=url,
            status=None,
            raw_html="",
            fetched_at=datetime.now(timezone.utc),
            error=f"Invalid or unsupported URL: {url}",
        )

    client = _get_client()
    try:
        request_headers = _build_headers()
        if if_none_match or if_modified_since:
            if if_none_match:
                request_headers["If-None-Match"] = if_none_match
            if if_modified_since:
                request_headers["If-Modified-Since"] = if_modified_since
            resp = client.get(url, timeout=timeout, headers=request_headers)
        else:
            resp = client.get(url, timeout=timeout, headers=request_headers)
        fetched_at = datetime.now(timezone.utc)
        try:
            resp_headers = dict(resp.headers)
        except Exception:
            resp_headers = {}

        etag = resp.headers.get("etag")
        last_modified = resp.headers.get("last-modified")

        content_type = (resp.headers.get("content-type") or "").lower()
        content_type_warning = bool(
            content_type and "text/html" not in content_type
            and "application/json" not in content_type
            and "text/plain" not in content_type
            and "application/xml" not in content_type
            and "+xml" not in content_type
        )

        if resp.status_code == 304:
            return FetchResult(
                url=url,
                status=304,
                raw_html="",
                fetched_at=fetched_at,
                error=None,
                raw_headers=resp_headers,
                etag=etag,
                last_modified=last_modified,
                not_modified=True,
                content_type_warning=content_type_warning,
            )

        if resp.status_code >= 400:
            return FetchResult(
                url=url,
                status=resp.status_code,
                raw_html="",
                fetched_at=fetched_at,
                error=f"HTTP {resp.status_code}: {resp.reason_phrase}",
                raw_headers=resp_headers,
                etag=etag,
                last_modified=last_modified,
                content_type_warning=content_type_warning,
            )

        return FetchResult(
            url=url,
            status=resp.status_code,
            raw_html=resp.text,
            fetched_at=fetched_at,
            error=None,
            raw_headers=resp_headers,
            etag=etag,
            last_modified=last_modified,
            content_type_warning=content_type_warning,
        )

    except httpx.TimeoutException as exc:
        return FetchResult(
            url=url,
            status=None,
            raw_html="",
            fetched_at=datetime.now(timezone.utc),
            error=f"Timeout after {timeout}s: {exc}",
        )
    except httpx.ConnectError as exc:
        return FetchResult(
            url=url,
            status=None,
            raw_html="",
            fetched_at=datetime.now(timezone.utc),
            error=f"Connection error: {exc}",
        )
    except httpx.RemoteProtocolError as exc:
        return FetchResult(
            url=url,
            status=None,
            raw_html="",
            fetched_at=datetime.now(timezone.utc),
            error=f"Protocol error: {exc}",
        )
    except httpx.StreamError as exc:
        error_msg = str(exc)
        if "too large" in error_msg.lower() or "max_response_body_size" in error_msg:
            return FetchResult(
                url=url,
                status=None,
                raw_html="",
                fetched_at=datetime.now(timezone.utc),
                error=f"Response too large (limit: {_DEFAULT_MAX_RESPONSE_BYTES} bytes): {exc}",
            )
        return FetchResult(
            url=url,
            status=None,
            raw_html="",
            fetched_at=datetime.now(timezone.utc),
            error=f"Stream error: {exc}",
        )
    except httpx.HTTPError as exc:
        return FetchResult(
            url=url,
            status=None,
            raw_html="",
            fetched_at=datetime.now(timezone.utc),
            error=f"HTTP error: {exc}",
        )
    except Exception as exc:
        return FetchResult(
            url=url,
            status=None,
            raw_html="",
            fetched_at=datetime.now(timezone.utc),
            error=f"Request failed: {type(exc).__name__}: {exc}",
        )
