from fastapi.testclient import TestClient

from app.main import create_app


def test_radar_endpoint_returns_scores() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/radar/threat-opportunity",
        json={
            "url": "https://medai.example",
            "title": "MedAI",
            "extracted_text": (
                "MedAI automates healthcare workflows with AI agents and LLM copilots. "
                "The platform uses OpenAI APIs and has latency pressure."
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["wrapper_risk"] >= 0.7
    assert body["nvidia_fit"] >= 0.7
    assert body["recommended_focus"]
