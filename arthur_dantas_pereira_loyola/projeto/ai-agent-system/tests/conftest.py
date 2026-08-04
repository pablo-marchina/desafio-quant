from __future__ import annotations

import pytest

from radar.settings import get_settings


@pytest.fixture(autouse=True)
def disable_external_providers_for_unit_tests(monkeypatch: pytest.MonkeyPatch):
    """Keep unit tests deterministic even when the local .env enables providers."""

    monkeypatch.setenv("RADAR_ENABLE_EXTERNAL_PROVIDERS", "false")
    monkeypatch.setenv("RADAR_SEARCH_PROVIDER", "fixture")
    monkeypatch.setenv("RADAR_PAGE_PROVIDER", "fixture")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()