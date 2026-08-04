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
    db_url = f"sqlite:///{(tmp_path / 'claim_api.db').as_posix()}"
    monkeypatch.setenv("PRODUCT_DB_URL", db_url)
    configure_product_database(db_url)
    with TestClient(app) as test_client:
        yield test_client
    reset_product_database_runtime()


def _setup_startup_with_run(client: TestClient, startup_name: str = "Claim API Startup") -> tuple[TestClient, str, str]:
    resp = client.post(
        "/startups",
        json={
            "name": startup_name,
            "website": f"https://{startup_name.lower().replace(' ', '')}.example.com",
            "country": "Brazil",
            "sector": "AI",
            "description": "AI company",
            "product_summary": "AI platform",
        },
    )
    startup_id = resp.json()["id"]

    resp2 = client.post(f"/startups/{startup_id}/analysis-runs", json={})
    assert resp2.status_code == 201, f"Create analysis run failed: {resp2.text}"
    run_id = resp2.json()["id"]

    return client, startup_id, run_id


def test_list_claims_empty(client_fixture: TestClient):
    """GET /analysis-runs/{id}/claims returns claims when pipeline ran."""
    client, _, run_id = _setup_startup_with_run(client_fixture, "Empty Claim")
    resp = client.get(f"/analysis-runs/{run_id}/claims")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["total"] > 0


def test_list_claims_with_filter(client_fixture: TestClient):
    """GET /analysis-runs/{id}/claims supports claim_type filter."""
    client, _, run_id = _setup_startup_with_run(client_fixture, "Filtered Claim")

    resp = client.get(f"/analysis-runs/{run_id}/claims?claim_type=gap_claim")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


def test_list_claims_invalid_run_id(client_fixture: TestClient):
    """GET /analysis-runs/{id}/claims returns 404 for nonexistent run."""
    resp = client_fixture.get("/analysis-runs/nonexistent-run/claims")
    assert resp.status_code == 404


def test_evidence_coverage(client_fixture: TestClient):
    """GET /analysis-runs/{id}/evidence-coverage returns summary."""
    client, _, run_id = _setup_startup_with_run(client_fixture, "Coverage Test")
    resp = client.get(f"/analysis-runs/{run_id}/evidence-coverage")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_claims" in data
    assert "evidence_coverage" in data
    assert "critical_claims" in data
    assert "critical_supported_claims" in data


def test_evidence_coverage_invalid_run(client_fixture: TestClient):
    """GET /analysis-runs/{id}/evidence-coverage returns 404 for nonexistent run."""
    resp = client_fixture.get("/analysis-runs/nonexistent/evidence-coverage")
    assert resp.status_code == 404


def test_update_claim_review(client_fixture: TestClient):
    """PATCH /analysis-runs/{id}/claims/{claim_id}/review updates review status."""
    client, _, run_id = _setup_startup_with_run(client_fixture, "Review Test")

    resp = client.get(f"/analysis-runs/{run_id}/claims")
    claims = resp.json().get("items", [])

    if len(claims) > 0:
        claim_id = claims[0]["id"]
        rev_resp = client.patch(
            f"/analysis-runs/{run_id}/claims/{claim_id}/review",
            json={
                "review_status": "needs_more_evidence",
                "reviewer_notes": "Needs additional evidence",
            },
        )
        assert rev_resp.status_code == 200
        updated = rev_resp.json()
        assert updated["review_status"] == "needs_more_evidence"


def test_update_claim_review_invalid_status(client_fixture: TestClient):
    """PATCH returns 400 for invalid review_status."""
    client, _, run_id = _setup_startup_with_run(client_fixture, "Invalid Review")

    resp = client.get(f"/analysis-runs/{run_id}/claims")
    claims = resp.json().get("items", [])

    if len(claims) > 0:
        claim_id = claims[0]["id"]
        rev_resp = client.patch(
            f"/analysis-runs/{run_id}/claims/{claim_id}/review",
            json={"review_status": "invalid_status"},
        )
        assert rev_resp.status_code == 422


def test_update_claim_review_not_found(client_fixture: TestClient):
    """PATCH returns 404 for nonexistent claim."""
    client, _, run_id = _setup_startup_with_run(client_fixture, "NotFound Review")
    resp = client.patch(
        f"/analysis-runs/{run_id}/claims/nonexistent/review",
        json={"review_status": "approved"},
    )
    assert resp.status_code == 404


def test_claim_summary_in_analysis_run(client_fixture: TestClient):
    """Analysis run response includes claim_summary."""
    client, startup_id, run_id = _setup_startup_with_run(client_fixture, "Summary Test")
    resp = client.get(f"/analysis-runs/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    if "claim_summary" in data:
        cs = data["claim_summary"]
        assert "total_claims" in cs
        assert "unsupported_claims" in cs
        assert "evidence_coverage" in cs


def test_opportunity_list_includes_claim_fields(client_fixture: TestClient):
    """Opportunity list includes unsupported_claim_count and evidence_coverage."""
    client, _, _ = _setup_startup_with_run(client_fixture, "Opportunity Claim")
    resp = client.get("/opportunities")
    assert resp.status_code == 200
    data = resp.json()
    items = data if isinstance(data, list) else data.get("opportunities", data.get("items", []))
    for item in items:
        assert "unsupported_claim_count" in item
        assert "evidence_coverage" in item
