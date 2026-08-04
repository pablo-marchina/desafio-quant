from fastapi.testclient import TestClient

from app.main import create_app
from app.rag.chunking import chunk_text
from app.rag.ingestion import prepare_seed_knowledge_documents
from app.rag.search import search_technology_catalog


def test_chunk_text_overlaps_long_text() -> None:
    text = " ".join(f"word-{index}" for index in range(20))

    chunks = chunk_text(text, max_words=10, overlap_words=2)

    assert len(chunks) == 3
    assert chunks[0].endswith("word-9")
    assert chunks[1].startswith("word-8")


def test_prepare_seed_knowledge_documents_has_sources_and_chunks() -> None:
    documents = prepare_seed_knowledge_documents()

    assert documents
    assert all(document.url.startswith("https://") for document in documents)
    assert all(document.chunks for document in documents)


def test_search_technology_catalog_matches_latency_query() -> None:
    results = search_technology_catalog("llm inference latency optimization", limit=3)
    result_names = {result.name for result in results}

    assert "TensorRT-LLM" in result_names
    assert "NVIDIA Triton Inference Server" in result_names


def test_knowledge_api_lists_technologies() -> None:
    client = TestClient(create_app())

    response = client.get("/knowledge/technologies")

    assert response.status_code == 200
    assert any(item["name"] == "NVIDIA NIM" for item in response.json())


def test_knowledge_api_searches_catalog() -> None:
    client = TestClient(create_app())

    response = client.post("/knowledge/search", json={"query": "voice transcription", "limit": 5})

    assert response.status_code == 200
    assert response.json()[0]["name"] == "NVIDIA Riva"
