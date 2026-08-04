from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from requests import RequestException


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.config import Settings
from app.main import app, get_embedder, get_settings, get_vector_store


class FakeEmbedder:
    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    def embed_passage(self, text: str) -> list[float]:
        return self.embed(text)


class FakeVectorStore:
    def __init__(self) -> None:
        self.upserted_points = []

    def health(self) -> dict[str, object]:
        return {"status": "ok", "version": "test"}

    def ensure_collection(self, collection_name: str, recreate: bool = False) -> None:
        self.collection_name = collection_name
        self.recreate = recreate

    def upsert_points(self, collection_name: str, points: list[dict[str, object]]) -> None:
        self.upserted_points.extend(points)

    def search(
        self,
        collection_name: str,
        vector: list[float],
        limit: int,
        filters: dict[str, object] | None = None,
    ) -> list[dict[str, object]]:
        return [
            {
                "score": 0.82,
                "payload": {
                    "product_name": "NVIDIA NIM",
                    "category": "model_deployment",
                    "source_url": "https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/",
                    "chunk_text": "NIM ajuda com deploy de inferencia em producao e latencia.",
                    "source_type": "seed",
                    "summary": "Optimized inference microservices.",
                    "chunk_index": 0,
                },
            },
            {
                "score": 0.7,
                "payload": {
                    "product_name": "NVIDIA RAPIDS",
                    "category": "data_processing",
                    "source_url": "https://rapids.ai/",
                    "chunk_text": "RAPIDS acelera pipelines de dados.",
                    "source_type": "seed",
                    "summary": "GPU data science.",
                    "chunk_index": 0,
                },
            },
        ][:limit]


class UnavailableVectorStore(FakeVectorStore):
    def health(self) -> dict[str, object]:
        raise RequestException("connection refused")


class WeakEvidenceVectorStore(FakeVectorStore):
    def search(
        self,
        collection_name: str,
        vector: list[float],
        limit: int,
        filters: dict[str, object] | None = None,
    ) -> list[dict[str, object]]:
        return [
            {
                "score": 0.1,
                "payload": {
                    "product_name": "NVIDIA NIM",
                    "category": "model_deployment",
                    "source_url": "",
                    "chunk_text": "Trecho curto.",
                    "source_type": "seed",
                    "summary": "Weak source.",
                    "chunk_index": 0,
                },
            }
        ][:limit]


class ApiEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.vector_store = FakeVectorStore()
        app.dependency_overrides[get_settings] = lambda: Settings(
            database_url=None,
            embedding_provider="hash",
            vector_size=3,
            startup_source_path="data/startups_br.csv",
        )
        app.dependency_overrides[get_vector_store] = lambda: self.vector_store
        app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_health_uses_dependency_overrides(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["qdrant"]["status"], "ok")
        self.assertEqual(body["postgres"]["status"], "not_configured")
        self.assertEqual(body["reranker"]["provider"], "hybrid")

    def test_health_degrades_when_qdrant_is_unavailable(self) -> None:
        self.vector_store = UnavailableVectorStore()

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "degraded")
        self.assertEqual(body["qdrant"]["status"], "unavailable")
        self.assertIn("connection refused", body["qdrant"]["error"])
        self.assertEqual(body["postgres"]["status"], "not_configured")

    def test_rag_search_returns_contract_without_qdrant(self) -> None:
        response = self.client.post(
            "/rag/search",
            json={"query": "latencia de inferencia LLM", "limit": 2},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["query"], "latencia de inferencia LLM")
        self.assertEqual(body["results"][0]["product_name"], "NVIDIA NIM")
        self.assertIn("metadata", body["results"][0])
        self.assertEqual(body["results"][0]["metadata"]["rerank"]["provider"], "hybrid")
        self.assertIn("final_score", body["results"][0]["metadata"]["rerank"])
        self.assertIn("bm25_score", body["results"][0]["metadata"]["rerank"])

    def test_admin_endpoint_requires_token_when_configured(self) -> None:
        app.dependency_overrides[get_settings] = lambda: Settings(
            database_url=None,
            embedding_provider="hash",
            vector_size=3,
            startup_source_path="data/startups_br.csv",
            admin_api_token="secret",
        )

        response = self.client.post("/rag/ingest/nvidia", json={"reset_collection": False})

        self.assertEqual(response.status_code, 401)

    def test_admin_endpoint_accepts_configured_token(self) -> None:
        app.dependency_overrides[get_settings] = lambda: Settings(
            database_url=None,
            embedding_provider="hash",
            vector_size=3,
            startup_source_path="data/startups_br.csv",
            admin_api_token="secret",
        )

        response = self.client.post(
            "/rag/ingest/nvidia",
            json={"reset_collection": False},
            headers={"X-Admin-Token": "secret"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["collection_name"], "nvidia_knowledge_base")
        self.assertGreaterEqual(body["documents"], 1)

    def test_startup_radar_works_from_csv_without_database(self) -> None:
        response = self.client.post(
            "/startup/radar",
            json={"sector": "logistics", "focus": "rotas scheduling", "limit": 3},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(body["returned"], 1)
        names = [item["startup_name"] for item in body["results"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(body["results"][0]["top_tools"][0]["technology"], "NVIDIA cuOpt")
        self.assertIn(body["results"][0]["approach_timing"], ["quente", "morno", "exploratorio"])
        self.assertIn("source_confidence", body["results"][0])
        self.assertIn("source_summary", body["results"][0])
        self.assertIn("source_evidence", body["results"][0])

    def test_startup_analysis_returns_recommendations_without_database(self) -> None:
        response = self.client.post(
            "/analysis/startup",
            json={
                "startup_name": "Demo AI",
                "sector": "healthcare",
                "description": "Startup usa LLM, workflow e inferencia em producao.",
                "technical_gaps": ["latencia de inferencia"],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["startup_name"], "Demo AI")
        self.assertGreaterEqual(len(body["recommendations"]), 1)
        self.assertEqual(body["recommendations"][0]["rerank_details"]["provider"], "hybrid")
        self.assertIn("implementation_complexity", body["recommendations"][0])
        self.assertIn("next_action", body["recommendations"][0])
        self.assertEqual(body["search_plan"]["version"], "search_plan_v1")
        self.assertIn("Demo AI", body["search_plan"]["search_terms"])
        self.assertGreaterEqual(len(body["pipeline_trace"]), 6)
        self.assertEqual(body["pipeline_trace"][0]["agent"], "Search Planner Agent")
        self.assertEqual(
            body["pipeline_trace"][0]["metadata"]["search_plan_version"],
            "search_plan_v1",
        )
        self.assertIn("Briefing executivo", body["briefing_markdown"])
        self.assertIn("Plano de busca", body["briefing_markdown"])
        self.assertIn("Reranking: hybrid", body["briefing_markdown"])
        self.assertIn("BM25", body["briefing_markdown"])
        self.assertIn("Pipeline executada", body["briefing_markdown"])
        self.assertIn("Playbook de abordagem NVIDIA", body["briefing_markdown"])
        self.assertIn("structured_profile", body)
        self.assertTrue(body["structured_profile"]["technologies"])
        self.assertTrue(body["structured_profile"]["ai_signals"])

    def test_startup_analysis_filters_blocked_recommendations(self) -> None:
        self.vector_store = WeakEvidenceVectorStore()

        response = self.client.post(
            "/analysis/startup",
            json={
                "startup_name": "Demo AI",
                "sector": "healthcare",
                "description": "Startup usa LLM, workflow e inferencia em producao.",
                "technical_gaps": ["latencia de inferencia"],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["recommendations"], [])
        self.assertTrue(
            any(
                check["claim_type"] == "recommendation"
                and check["blocks_recommendation"]
                and check["blocking_reason"]
                for check in body["evidence_checks"]
            )
        )
        self.assertTrue(
            any("Evidence Validator bloqueou" in limitation for limitation in body["limitations"])
        )

    def test_freshness_check_endpoint_can_be_mocked_without_network(self) -> None:
        mocked_checks = [
            {
                "product_name": "NVIDIA NIM",
                "category": "model_deployment",
                "source_url": "https://example.test/nim",
                "checked_at": "2026-06-26T00:00:00+00:00",
                "status": "changed",
                "action": "ingest_candidate",
                "local_content_hash": "old",
                "remote_content_hash": "new",
                "local_modified_at": None,
                "remote_modified_at": None,
                "characters": 1200,
                "is_useful_for_startups": True,
                "usefulness_score": 48,
                "useful_topics": ["model_deployment"],
                "usefulness_reason": "Conteudo util para deployment.",
                "error": None,
            }
        ]
        with patch("app.main.check_nvidia_sources", return_value=mocked_checks):
            response = self.client.post(
                "/rag/freshness/check",
                json={"max_sources": 1, "persist_results": False},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["checked"], 1)
        self.assertEqual(body["changed"], 1)
        self.assertFalse(body["persisted"])

    def test_saved_briefing_markdown_endpoint_returns_downloadable_text(self) -> None:
        mocked_briefing = {
            "analysis_run_id": "11111111-1111-1111-1111-111111111111",
            "startup_name": "Demo AI",
            "created_at": "2026-06-26T00:00:00+00:00",
            "briefing_markdown": "# Briefing executivo - Demo AI\n",
        }
        with patch("app.main.get_analysis_briefing", return_value=mocked_briefing):
            response = self.client.get(
                "/analysis/runs/11111111-1111-1111-1111-111111111111/briefing.md"
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/markdown", response.headers["content-type"])
        self.assertIn("Briefing executivo", response.text)

    def test_saved_briefing_pdf_endpoint_returns_pdf(self) -> None:
        mocked_briefing = {
            "analysis_run_id": "11111111-1111-1111-1111-111111111111",
            "startup_name": "Demo AI",
            "created_at": "2026-06-26T00:00:00+00:00",
            "briefing_markdown": "# Briefing executivo - Demo AI\n",
        }
        with patch("app.main.get_analysis_briefing", return_value=mocked_briefing):
            response = self.client.get(
                "/analysis/runs/11111111-1111-1111-1111-111111111111/briefing.pdf"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-1.4"))


if __name__ == "__main__":
    unittest.main()
