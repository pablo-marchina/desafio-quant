"""Integration tests for Activation Dossier API endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.database.session import configure_product_database, reset_product_database_runtime
from src.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_url = f"sqlite:///{(tmp_path / 'dossier_api.db').as_posix()}"
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("PRODUCT_DB_URL", db_url)
    monkeypatch.setenv("ENABLE_PRODUCT_PERSISTENCE", "true")
    configure_product_database(db_url)
    with TestClient(app) as c:
        yield c
    reset_product_database_runtime()


def _create_startup_and_run(client) -> tuple[str, str]:
    resp = client.post(
        "/startups",
        json={
            "name": "Dossier API Test",
            "website": "https://dossier-api.example.com",
            "sector": "AI",
            "evidence": [
                {
                    "claim": "Uses AI in production",
                    "source_url": "https://dossier-api.example.com",
                    "source_type": "official_site",
                    "quote_or_evidence": "AI production usage",
                    "confidence": "high",
                }
            ],
        },
    )
    assert resp.status_code == 201
    startup_id = resp.json()["id"]

    run_resp = client.post(f"/startups/{startup_id}/analysis-runs", json={"use_rag": False})
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]
    return startup_id, run_id


def test_post_dossier_creates_new(client) -> None:
    _, run_id = _create_startup_and_run(client)
    resp = client.post(f"/analysis-runs/{run_id}/dossier")
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_new"] is True
    assert data["version"] == 1
    dossier = data["dossier"]
    assert dossier["analysis_run_id"] == run_id
    assert dossier["schema_version"] == "1.0"
    assert dossier["is_latest"] is True
    assert dossier["dossier_json"] is not None
    assert dossier["dossier_markdown"] is not None
    assert isinstance(dossier["evidence_coverage"], float)
    assert isinstance(dossier["unsupported_claim_count"], int)


def test_post_dossier_idempotent_returns_existing(client) -> None:
    _, run_id = _create_startup_and_run(client)
    resp1 = client.post(f"/analysis-runs/{run_id}/dossier")
    assert resp1.status_code == 201
    v1_data = resp1.json()

    resp2 = client.post(f"/analysis-runs/{run_id}/dossier")
    assert resp2.status_code == 201
    v2_data = resp2.json()

    assert v2_data["is_new"] is False
    assert v2_data["dossier"]["id"] == v1_data["dossier"]["id"]


def test_post_dossier_force_new_version(client) -> None:
    _, run_id = _create_startup_and_run(client)
    resp1 = client.post(f"/analysis-runs/{run_id}/dossier")
    v1 = resp1.json()["dossier"]

    resp2 = client.post(f"/analysis-runs/{run_id}/dossier?force=true")
    assert resp2.status_code == 201
    v2 = resp2.json()["dossier"]
    assert v2["id"] != v1["id"]
    assert v2["version"] == 2
    assert v2["is_latest"] is True


def test_get_dossier_returns_latest(client) -> None:
    _, run_id = _create_startup_and_run(client)
    resp = client.get(f"/analysis-runs/{run_id}/dossier")
    assert resp.status_code == 404

    client.post(f"/analysis-runs/{run_id}/dossier")
    resp = client.get(f"/analysis-runs/{run_id}/dossier")
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_run_id"] == run_id
    assert data["version"] == 1
    assert data["is_latest"] is True


def test_get_dossier_markdown(client) -> None:
    _, run_id = _create_startup_and_run(client)
    resp = client.get(f"/analysis-runs/{run_id}/dossier/markdown")
    assert resp.status_code == 404

    client.post(f"/analysis-runs/{run_id}/dossier")
    resp = client.get(f"/analysis-runs/{run_id}/dossier/markdown")
    assert resp.status_code == 200
    data = resp.json()
    assert "markdown" in data
    assert "dossier_id" in data
    assert "# Startup Activation Dossier" in data["markdown"]


def test_dossier_404_for_nonexistent_run(client) -> None:
    resp = client.post("/analysis-runs/nonexistent/dossier")
    assert resp.status_code == 404

    resp = client.get("/analysis-runs/nonexistent/dossier")
    assert resp.status_code == 404

    resp = client.get("/analysis-runs/nonexistent/dossier/markdown")
    assert resp.status_code == 404


def test_dossier_summary_in_analysis_run(client) -> None:
    _, run_id = _create_startup_and_run(client)
    resp = client.get(f"/analysis-runs/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "dossier_summary" in data
    assert data["dossier_summary"]["dossier_available"] is False

    client.post(f"/analysis-runs/{run_id}/dossier")
    resp = client.get(f"/analysis-runs/{run_id}")
    data = resp.json()
    assert data["dossier_summary"]["dossier_available"] is True
    assert data["dossier_summary"]["dossier_id"] is not None


def test_dossier_opportunity_summary(client) -> None:
    _, run_id = _create_startup_and_run(client)
    client.post(f"/analysis-runs/{run_id}/dossier")
    resp = client.get("/opportunities")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) > 0
    item = data["items"][0]
    assert "dossier_available" in item
    assert "latest_dossier_id" in item
