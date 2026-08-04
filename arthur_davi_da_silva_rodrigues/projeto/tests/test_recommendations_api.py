from fastapi.testclient import TestClient

from app.main import create_app


def test_recommendations_endpoint_returns_nvidia_recommendations() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/recommendations",
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
    technology_names = {
        recommendation["technology_name"]
        for recommendation in body["recommendations"]
    }
    assert "NVIDIA NIM" in technology_names
    assert "TensorRT-LLM" in technology_names
    assert body["recommendations"][0]["source_url"].startswith("https://")
