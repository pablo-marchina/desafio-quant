from fastapi.testclient import TestClient

from app.main import create_app


def test_extract_startup_profile_endpoint_returns_evidence_buckets() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/extraction/startup-profile",
        json={
            "url": "https://medai.example",
            "title": "MedAI",
            "extracted_text": (
                "MedAI automates healthcare workflows with AI agents and LLM copilots. "
                "The platform uses OpenAI APIs."
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "MedAI"
    assert "healthcare" in body["sectors"]
    assert "LLM" in body["technology_signals"]
    assert body["accepted_claims"]
    assert body["review_claims"]
    assert body["evidence_claims"][0]["validation_status"] in {
        "accepted",
        "needs_review",
    }
