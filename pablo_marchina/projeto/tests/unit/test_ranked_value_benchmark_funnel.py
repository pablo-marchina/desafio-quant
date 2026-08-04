from __future__ import annotations

from scripts import rank_value_candidates, run_ranked_value_benchmarks


def test_ranking_prioritizes_graphrag_and_marks_non_executable() -> None:
    rows = [
        {
            "candidate_id": "runtime",
            "name": "Docker Compose",
            "category": "8.1 Runtime core",
            "status": "BENCHMARKED",
        },
        {
            "candidate_id": "graphrag",
            "name": "GraphRAG local search",
            "category": "8.4 Graph and GraphRAG",
            "status": "BENCHMARKED",
        },
        {
            "candidate_id": "hybrid",
            "name": "Hybrid retrieval",
            "category": "8.5 RAG/retrieval techniques",
            "status": "BENCHMARKED",
        },
    ]

    queue = rank_value_candidates.build_ranked_queue(rows)

    assert queue[0]["candidate_id"] == "graphrag"
    assert queue[0]["executable"] is False
    assert any(item["candidate_id"] == "hybrid" and item["executable"] is True for item in queue)


def test_ranking_allows_free_external_api_candidates() -> None:
    rows = [
        {
            "candidate_id": "free-api",
            "name": "Free external reranker",
            "category": "8.6 Reranking",
            "status": "FUTURE_RESEARCH",
            "required_configuration": "free tier public API; no paid credentials required",
            "benchmark": "direct free external API benchmark when network is enabled",
        },
        {
            "candidate_id": "paid-api",
            "name": "Paid external reranker",
            "category": "8.6 Reranking",
            "status": "FUTURE_RESEARCH",
            "required_configuration": "paid SaaS license and private access",
        },
    ]

    queue = rank_value_candidates.build_ranked_queue(rows)

    assert [item["candidate_id"] for item in queue] == ["free-api"]
    assert queue[0]["executable"] is True
    assert queue[0]["external_free_api_allowed"] is True
    assert "free external benchmark path" in queue[0]["ranking_rationale"]


def test_ranking_allows_registry_eligible_external_candidate() -> None:
    rows = [
        {
            "candidate_id": "external-registry",
            "name": "Phoenix",
            "category": "8.12 LLMOps",
            "status": "FUTURE_RESEARCH",
            "required_configuration": "external service access",
        }
    ]

    queue = rank_value_candidates.build_ranked_queue(rows, free_external_names={"Phoenix"})

    assert len(queue) == 1
    assert queue[0]["candidate_id"] == "external-registry"
    assert queue[0]["executable"] is True
    assert queue[0]["external_free_api_allowed"] is True


def test_ranked_runner_stops_after_no_lift_window(monkeypatch) -> None:
    queue = [
        {
            "candidate_id": "graphrag",
            "name": "GraphRAG local search",
            "category": "8.4 Graph and GraphRAG",
            "priority_score": 130,
            "executable": False,
            "benchmark_key": "",
        },
        {
            "candidate_id": "bm25",
            "name": "BM25",
            "category": "8.3 Vector search / retrieval",
            "priority_score": 90,
            "executable": True,
            "benchmark_key": "rag_mode_quality",
        },
        {
            "candidate_id": "hybrid",
            "name": "Hybrid retrieval",
            "category": "8.5 RAG/retrieval techniques",
            "priority_score": 85,
            "executable": True,
            "benchmark_key": "rag_mode_quality",
        },
        {
            "candidate_id": "rrf",
            "name": "Reciprocal Rank Fusion",
            "category": "8.5 RAG/retrieval techniques",
            "priority_score": 84,
            "executable": True,
            "benchmark_key": "rag_mode_quality",
        },
        {
            "candidate_id": "late",
            "name": "fusion retrieval",
            "category": "8.5 RAG/retrieval techniques",
            "priority_score": 83,
            "executable": True,
            "benchmark_key": "rag_mode_quality",
        },
    ]

    def fake_quality_lift(name: str) -> dict[str, object]:
        return {
            "baseline_quality_score": 1.0,
            "candidate_quality_score": 1.0,
            "quality_delta": 0.0,
            "improved_quality": False,
            "candidate_mode": name,
        }

    monkeypatch.setattr(run_ranked_value_benchmarks, "_rag_quality_lift", fake_quality_lift)

    report = run_ranked_value_benchmarks.run_ranked_benchmarks(queue, patience=3, max_queue_scan=5)

    assert report["executed_count"] == 3
    assert report["implementation_required_count"] == 1
    assert report["reject_no_lift_count"] == 3
    assert report["stopped_before_benchmark_count"] == 1
    assert report["stop_reason"] == "NO_QUALITY_LIFT_IN_LAST_3_EXECUTABLE_BENCHMARKS"


def test_ranked_runner_resets_stop_window_on_adoption(monkeypatch) -> None:
    queue = [
        {
            "candidate_id": "a",
            "name": "BM25",
            "category": "8.3 Vector search / retrieval",
            "priority_score": 90,
            "executable": True,
            "benchmark_key": "rag_mode_quality",
        },
        {
            "candidate_id": "b",
            "name": "Hybrid retrieval",
            "category": "8.5 RAG/retrieval techniques",
            "priority_score": 85,
            "executable": True,
            "benchmark_key": "rag_mode_quality",
        },
        {
            "candidate_id": "c",
            "name": "Reciprocal Rank Fusion",
            "category": "8.5 RAG/retrieval techniques",
            "priority_score": 84,
            "executable": True,
            "benchmark_key": "rag_mode_quality",
        },
    ]
    deltas = {"BM25": 0.0, "Hybrid retrieval": 0.02, "Reciprocal Rank Fusion": 0.0}

    def fake_quality_lift(name: str) -> dict[str, object]:
        delta = deltas[name]
        return {
            "baseline_quality_score": 1.0,
            "candidate_quality_score": 1.0 + delta,
            "quality_delta": delta,
            "improved_quality": delta > 0,
            "candidate_mode": name,
        }

    monkeypatch.setattr(run_ranked_value_benchmarks, "_rag_quality_lift", fake_quality_lift)

    report = run_ranked_value_benchmarks.run_ranked_benchmarks(queue, patience=2, max_queue_scan=3)

    assert report["executed_count"] == 3
    assert report["adopt_count"] == 1
    assert report["stop_reason"] == "QUEUE_EXHAUSTED"
