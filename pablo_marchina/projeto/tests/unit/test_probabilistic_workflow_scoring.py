from __future__ import annotations

import src.orchestration.node_impl  # noqa: F401
from src.orchestration.nodes import WORKFLOW_NODES
from src.orchestration.probabilistic_scoring import build_probabilistic_score
from src.orchestration.state import ProductWorkflowState


def _node(name: str):
    return next(node for node in WORKFLOW_NODES if node.name == name)


def _profile() -> dict[str, object]:
    return {
        "startup_name": "ScoreAI",
        "website": "https://score.example.com",
        "sector": "AI Infrastructure",
        "description": "AI inference optimization platform.",
        "product_summary": "Optimizes TensorRT inference workloads.",
        "ai_signals": ["AI inference"],
        "tech_stack_signals": ["TensorRT", "CUDA"],
        "sources": [],
        "confidence_score": 0.74,
    }


def _evidence() -> list[dict[str, object]]:
    return [
        {
            "id": "ev-score-1",
            "source": "official_site",
            "source_type": "official_site",
            "source_reliability": 0.9,
            "relevance": 0.82,
            "claim": "Runs optimized inference workloads.",
        },
        {
            "id": "ev-score-2",
            "source": "technical_blog",
            "source_type": "blog",
            "source_quality_score": 0.7,
            "evidence_confidence_score": 0.76,
            "claim": "Uses CUDA and TensorRT.",
        },
    ]


def test_probabilistic_score_records_missing_metrics_instead_of_midpoint_defaults() -> None:
    result = build_probabilistic_score(
        evidence_items=[{"id": "ev-missing", "claim": "Unscored evidence"}],
        startup_profile={"confidence_score": 0.7},
    )

    assert result["evidence_coverage"] < 1.0
    assert "evidence_ev-missing.source_reliability" in result["missing_metrics"]
    assert "evidence_ev-missing.relevance" in result["missing_metrics"]
    evidence_features = [item for item in result["features"] if item["name"] == "evidence_ev-missing"]
    assert evidence_features[0]["bounded_value"] == 0.0
    assert result["uncertainty"] > 0


def test_single_score_node_writes_probabilistic_and_evidence_weighted_scores() -> None:
    base_state = ProductWorkflowState(
        workflow_id="wf-score",
        startup_profile=_profile(),
        evidence_items=_evidence(),
        node_outputs={"validated_evidence": _evidence()},
    )

    scored = _node("score_startup_probabilistic").fn(base_state)
    assert scored.status == "completed"

    startup_score = scored.state_updates["scores"]
    weighted_score = scored.state_updates["evidence_weighted_scores"]
    assert weighted_score["score"] == startup_score["score"]
    assert weighted_score["formula"] == startup_score["formula"]
    assert weighted_score["evidence_ids_used"] == startup_score["evidence_ids_used"]
