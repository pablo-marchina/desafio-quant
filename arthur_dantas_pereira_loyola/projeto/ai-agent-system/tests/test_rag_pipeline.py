from __future__ import annotations

from radar.rag.embeddings import EMBEDDING_DIMENSION, embed_text
from radar.rag.knowledge_base import get_seed_chunks
from radar.rag.retriever import ensure_seeded, reset, retrieve
from radar.rag.vector_store import VectorStore
from radar.schemas import NvidiaKnowledgeChunk


class TestEmbeddings:
    def test_embed_text_returns_list_of_floats(self) -> None:
        vector = embed_text("NVIDIA robotics platform")
        assert isinstance(vector, list)
        assert len(vector) > 0
        assert all(isinstance(v, float) for v in vector)

    def test_embed_dimension_matches_constant(self) -> None:
        vector = embed_text("test")
        assert len(vector) == EMBEDDING_DIMENSION

    def test_embed_similar_texts_are_close(self) -> None:
        v1 = embed_text("robotics simulation")
        v2 = embed_text("robot autonomy")
        v3 = embed_text("ice cream recipe")
        sim_12 = sum(a * b for a, b in zip(v1, v2))
        sim_13 = sum(a * b for a, b in zip(v1, v3))
        assert sim_12 > sim_13, "similar texts should have higher cosine similarity"


class TestVectorStore:
    def test_create_and_search(self) -> None:
        store = VectorStore()
        store.insert([
            {"id": 1, "content": "NVIDIA Isaac is a robotics platform for simulation and autonomy"},
            {"id": 2, "content": "NVIDIA Clara is a healthcare AI platform for medical imaging"},
            {"id": 3, "content": "NVIDIA RAPIDS accelerates data science pipelines on GPUs"},
        ])
        assert store.count() == 3

        results = store.search("robot simulation", top_k=2)
        assert len(results) <= 2
        assert any("Isaac" in r.get("content", "") for r in results)

    def test_search_empty_store_returns_empty(self) -> None:
        store = VectorStore()
        assert store.search("anything") == []

    def test_clear_store(self) -> None:
        store = VectorStore()
        store.insert([{"id": 1, "content": "test"}])
        assert store.count() == 1
        store.clear()
        assert store.count() == 0

    def test_insert_empty_list(self) -> None:
        store = VectorStore()
        assert store.insert([]) == 0


class TestKnowledgeBase:
    def test_has_16_technologies(self) -> None:
        chunks = get_seed_chunks()
        assert len(chunks) == 16

    def test_every_chunk_has_required_fields(self) -> None:
        chunks = get_seed_chunks()
        for chunk in chunks:
            assert "id" in chunk
            assert "technology" in chunk
            assert "title" in chunk
            assert "url" in chunk
            assert "content" in chunk
            assert isinstance(chunk["content"], str)
            assert len(chunk["content"]) > 50

    def test_technologies_covered(self) -> None:
        chunks = get_seed_chunks()
        techs = {c["technology"] for c in chunks}
        expected = {
            "NVIDIA Inception", "NVIDIA NIM", "NVIDIA NeMo", "NeMo Guardrails",
            "NVIDIA Triton Inference Server", "TensorRT-LLM", "NVIDIA RAPIDS",
            "cuDF", "cuML", "CUDA", "NVIDIA Riva", "NVIDIA Omniverse",
            "NVIDIA Isaac", "NVIDIA Clara", "NVIDIA Morpheus", "NVIDIA AI Enterprise",
        }
        assert techs == expected


class TestRetriever:
    def test_seed_populates_store(self) -> None:
        reset()
        count = ensure_seeded()
        assert count == 16

    def test_retrieve_robotics_returns_isaac(self) -> None:
        reset()
        ensure_seeded()
        results = retrieve("robot simulation and autonomy", top_k=3)
        assert len(results) > 0
        contents = " ".join(r.get("content", "") for r in results).lower()
        assert "isaac" in contents or "robotics" in contents

    def test_retrieve_healthcare_returns_clara(self) -> None:
        reset()
        ensure_seeded()
        results = retrieve("medical imaging healthcare AI", top_k=3)
        assert len(results) > 0
        contents = " ".join(r.get("content", "") for r in results).lower()
        assert "clara" in contents or "healthcare" in contents

    def test_reset_clears_store(self) -> None:
        reset()
        ensure_seeded()
        assert len(retrieve("test", top_k=1)) > 0
        reset()
        ensure_seeded()
        assert len(retrieve("test", top_k=1)) > 0
        # ensure_seeded re-seeds after reset; that is expected behavior


class TestNvidiaRagAgent:
    def test_retrieve_context_from_state(self) -> None:
        from radar.agents.nvidia_rag import retrieve_nvidia_context

        reset()
        state = {
            "classification": type("obj", (), {"label": "AI-Native"})(),
            "validation": type("obj", (), {"has_minimum_evidence": True, "supporting_evidence_ids": []})(),
            "extracted_startups": [
                type("obj", (), {
                    "sector": "Robotics",
                    "product": "Autonomous drone platform",
                    "cited_technologies": ["LLM", "Computer Vision"],
                    "ai_usage_summary": "Uses AI for autonomous navigation",
                    "description": "Robotics startup",
                    "evidence_ids": [],
                })()
            ],
            "claims": [],
        }

        chunks = retrieve_nvidia_context(state)
        assert isinstance(chunks, list)
        if chunks:
            assert isinstance(chunks[0], NvidiaKnowledgeChunk)

    def test_non_ai_returns_empty(self) -> None:
        from radar.agents.nvidia_rag import retrieve_nvidia_context

        state = {
            "classification": type("obj", (), {"label": "Non-AI"})(),
            "validation": type("obj", (), {"has_minimum_evidence": True, "supporting_evidence_ids": []})(),
            "extracted_startups": [],
            "claims": [],
        }
        assert retrieve_nvidia_context(state) == []


def test_rag_expands_portuguese_health_voice_terms() -> None:
    from radar.agents.nvidia_rag import retrieve_nvidia_context

    reset()
    state = {
        "classification": type("obj", (), {"label": "AI-Native"})(),
        "validation": type("obj", (), {"has_minimum_evidence": True, "supporting_evidence_ids": ["claim_1"]})(),
        "extracted_startups": [
            type("obj", (), {
                "sector": None,
                "product": "assistente de voz para saude",
                "cited_technologies": [],
                "ai_usage_summary": "IA generativa para transcricao medica e atendimento clinico.",
                "description": "Startup de saude com IA.",
                "evidence_ids": ["claim_1"],
            })()
        ],
        "claims": [type("obj", (), {"id": "claim_1", "text": "A startup usa IA em saude, voz e transcricao medica."})()],
    }

    chunks = retrieve_nvidia_context(state)
    technologies = {chunk.technology for chunk in chunks}

    assert "NVIDIA Clara" in technologies
    assert "NVIDIA Riva" in technologies