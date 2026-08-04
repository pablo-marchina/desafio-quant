from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.database.session import configure_product_database, reset_product_database_runtime


@pytest.fixture
def client_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("ENABLE_PRODUCT_PERSISTENCE", "true")
    monkeypatch.setenv("QDRANT_URL", "")
    db_url = f"sqlite:///{(tmp_path / 'activation_api.db').as_posix()}"
    monkeypatch.setenv("PRODUCT_DB_URL", db_url)
    configure_product_database(db_url)
    with TestClient(app) as test_client:
        yield test_client
    reset_product_database_runtime()


def _setup_run(client: TestClient) -> tuple[TestClient, str, str]:
    resp = client.post(
        "/startups",
        json={
            "name": "Activation Test Startup",
            "website": "https://activation-test.example.com",
            "country": "Brazil",
            "sector": "AI",
            "description": "AI company for activation testing",
            "product_summary": "AI platform with inference needs",
        },
    )
    startup_id = resp.json()["id"]

    resp2 = client.post(f"/startups/{startup_id}/analysis-runs", json={})
    assert resp2.status_code == 201, f"Create analysis run failed: {resp2.text}"
    run_id = resp2.json()["id"]

    return client, startup_id, run_id


def test_get_playbooks_lists_all(client_fixture: TestClient) -> None:
    resp = client_fixture.get("/activation-playbooks")
    assert resp.status_code == 200
    data = resp.json()
    assert "playbooks" in data
    playbooks = data["playbooks"]
    assert len(playbooks) == 10
    ids = {pb["playbook_id"] for pb in playbooks}
    assert "latency_optimization" in ids
    assert "inference_cost_optimization" in ids


def test_list_recommendations_returns_items(client_fixture: TestClient) -> None:
    client, _, run_id = _setup_run(client_fixture)
    resp = client.get(f"/analysis-runs/{run_id}/activation-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "offset" in data
    assert "limit" in data


def test_generate_and_list_recommendations(client_fixture: TestClient) -> None:
    client, _, run_id = _setup_run(client_fixture)
    resp = client.post(f"/analysis-runs/{run_id}/activation-recommendations/generate")
    assert resp.status_code == 201
    data = resp.json()
    assert "recommendations" in data

    resp2 = client.get(f"/analysis-runs/{run_id}/activation-recommendations")
    assert resp2.status_code == 200
    list_data = resp2.json()
    assert len(list_data["items"]) == len(data["recommendations"])


def test_generate_is_idempotent(client_fixture: TestClient) -> None:
    client, _, run_id = _setup_run(client_fixture)
    resp1 = client.post(f"/analysis-runs/{run_id}/activation-recommendations/generate")
    assert resp1.status_code == 201
    count1 = len(resp1.json()["recommendations"])

    resp2 = client.post(f"/analysis-runs/{run_id}/activation-recommendations/generate")
    assert resp2.status_code == 201
    count2 = len(resp2.json()["recommendations"])

    assert count1 == count2


def test_get_recommendations_returns_404_for_nonexistent_run(client_fixture: TestClient) -> None:
    resp = client_fixture.get("/analysis-runs/nonexistent-run/activation-recommendations")
    assert resp.status_code == 404


def test_generate_recommendations_returns_404_for_nonexistent_run(
    client_fixture: TestClient,
) -> None:
    resp = client_fixture.post("/analysis-runs/nonexistent-run/activation-recommendations/generate")
    assert resp.status_code == 404


def test_recommendation_has_expected_fields(client_fixture: TestClient) -> None:
    client, _, run_id = _setup_run(client_fixture)
    resp = client.post(f"/analysis-runs/{run_id}/activation-recommendations/generate")
    assert resp.status_code == 201
    data = resp.json()
    recommendations = data["recommendations"]
    for rec in recommendations:
        assert "playbook_id" in rec
        assert "playbook_name" in rec
        assert "confidence" in rec
        assert "priority" in rec
        assert "recommended_motion" in rec
        assert "matched_gap_types" in rec
        assert isinstance(rec["matched_gap_types"], list)


def test_opportunities_include_activation_data(client_fixture: TestClient) -> None:
    client, startup_id, run_id = _setup_run(client_fixture)
    client.post(f"/analysis-runs/{run_id}/activation-recommendations/generate")

    resp = client.get("/opportunities")
    assert resp.status_code == 200
    data = resp.json()

    found = False
    for opp in data.get("opportunities", data.get("items", [])):
        if opp.get("startup_id") == startup_id:
            found = True
            assert "top_activation_playbook" in opp
            assert "activation_confidence" in opp
            assert "activation_next_step" in opp
    assert found, "Opportunity with activation data not found"
