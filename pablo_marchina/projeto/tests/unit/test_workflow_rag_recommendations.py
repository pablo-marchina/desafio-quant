from __future__ import annotations

import src.orchestration.node_impl  # noqa: F401
from src.orchestration.nodes import WORKFLOW_NODES
from src.orchestration.state import ProductWorkflowState


def _node(name: str):
    return next(node for node in WORKFLOW_NODES if node.name == name)


def _state() -> ProductWorkflowState:
    return ProductWorkflowState(
        workflow_id="wf-rag-rec",
        gap_ids=["high_inference_cost"],
        nvidia_contexts=[
            {
                "chunk_id": "rag-tensorrt-1",
                "source_id": "nvidia-docs",
                "title": "TensorRT",
                "content": "TensorRT optimizes inference on NVIDIA GPUs.",
                "product": "TensorRT",
                "gap_types": ["inference_performance_gap"],
                "url": "https://docs.nvidia.com/deeplearning/tensorrt/",
                "relevance_score": 0.92,
            }
        ],
        evidence_items=[
            {
                "id": "ev-tensorrt-1",
                "evidence_id": "ev-tensorrt-1",
                "text": "The startup uses TensorRT for GPU inference optimization.",
                "claim": "Uses TensorRT for inference optimization.",
                "source": "official_site",
                "source_type": "official_site",
                "evidence_confidence_score": 0.86,
                "source_quality_score": 0.82,
            }
        ],
        evidence_weighted_scores={
            "score": 0.78,
            "confidence": 0.74,
            "uncertainty": 0.16,
            "evidence_coverage": 0.8,
            "evidence_quality_mean": 0.84,
        },
        startup_profile={"startup_name": "TensorOps"},
    )


def test_map_nvidia_technologies_uses_rag_context_ids(monkeypatch) -> None:
    monkeypatch.delenv("APP_MODE", raising=False)
    state = _state()

    result = _node("map_nvidia_technologies").fn(state)

    assert result.status == "completed"
    mappings = result.state_updates["nvidia_mappings"]
    tensorrt = [item for item in mappings if item["nvidia_technology"] == "TensorRT"]
    assert tensorrt
    assert "rag-tensorrt-1" in tensorrt[0]["supporting_rag_context_ids"]
    assert "ev-tensorrt-1" in tensorrt[0]["supporting_evidence_ids"]


def test_recommendation_and_expected_utility_preserve_rag_support(monkeypatch) -> None:
    monkeypatch.delenv("APP_MODE", raising=False)
    state = _state()
    mapped = _node("map_nvidia_technologies").fn(state)
    state = state.model_copy(update=mapped.state_updates)

    recommended = _node("rank_recommendations").fn(state)
    assert recommended.status == "completed"
    state = state.model_copy(update=recommended.state_updates)

    ranked = _node("rank_with_expected_utility").fn(state)
    assert ranked.status == "completed"
    top = ranked.state_updates["ranked_recommendations"][0]
    assert top["supporting_rag_context_ids"]
    assert top["expected_utility"] > 0
