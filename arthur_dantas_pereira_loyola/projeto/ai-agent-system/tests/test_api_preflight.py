from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from radar.api import app as api_app
from radar.scraping.provider_preflight import inspect_provider_setup
from radar.settings import RadarSettings


def test_provider_preflight_endpoint_reports_default_fixture_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api_app,
        "inspect_provider_setup",
        lambda: inspect_provider_setup(RadarSettings()),
    )
    client = TestClient(api_app.app)

    response = client.get("/providers/preflight")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["search_provider"] == "fixture"
    assert payload["page_provider"] == "fixture"
    assert payload["external_providers_enabled"] is False
    assert payload["network_required"] is False
    assert payload["missing_credentials"] == []
    assert "fixture providers" in payload["messages"][0]