"""Pytest guards for module integration suites.

Integration tests should run when their local services are available and be
reported as explicit skips when the developer machine has no infra running.
This keeps the full module suite useful without hiding real unit failures.
"""

from __future__ import annotations

import socket
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import pytest

from apps.api.src.config.settings import get_settings


_NO_EXTERNAL_DEPS_INTEGRATION_TESTS = {
    "test_scraping_flow.py",
    "test_jinja_playwright_pdf_renderer.py",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(str(item.fspath))
        if "integration" not in path.parts:
            continue

        item.add_marker(pytest.mark.integration)

        required_services = _required_services(path)
        for service_name in required_services:
            item.add_marker(getattr(pytest.mark, service_name))

        unavailable = [
            service_name
            for service_name in required_services
            if not _service_is_available(service_name)
        ]
        if unavailable:
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        "integration service unavailable: "
                        + ", ".join(sorted(unavailable))
                    )
                )
            )


def _required_services(path: Path) -> set[str]:
    if path.name in _NO_EXTERNAL_DEPS_INTEGRATION_TESTS:
        return set()
    if "qdrant" in path.name:
        return {"qdrant"}
    if "distributed_worker" in path.name:
        return {"postgres", "redis"}
    return {"postgres"}


@lru_cache
def _service_is_available(service_name: str) -> bool:
    settings = get_settings()
    if service_name == "postgres":
        return _tcp_endpoint_is_available(settings.database_url)
    if service_name == "qdrant":
        return _tcp_endpoint_is_available(settings.qdrant_url)
    if service_name == "redis":
        return _tcp_endpoint_is_available(settings.redis_url)
    return False


def _tcp_endpoint_is_available(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or _default_port(parsed.scheme)
    if host is None or port is None:
        return False

    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def _default_port(scheme: str) -> int | None:
    normalized_scheme = scheme.split("+", maxsplit=1)[0]
    return {
        "http": 80,
        "https": 443,
        "postgresql": 5432,
        "redis": 6379,
    }.get(normalized_scheme)
