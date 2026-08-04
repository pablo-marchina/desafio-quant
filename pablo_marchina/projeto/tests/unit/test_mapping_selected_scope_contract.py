from __future__ import annotations

from src.diagnosis.gap_diagnosis_scoring import diagnose_gaps_quantitative
from src.diagnosis.schemas import GapType
from src.orchestration.node_impl import _runtime_decision_inventory
from src.recommendation.nvidia_technology_mapping import (
    GAP_TECHNOLOGY_CANDIDATES,
    build_nvidia_technology_mappings,
)


def test_mapping_only_builds_candidates_for_selected_gap_and_reviews_supported_low_score() -> None:
    evidence = [
        {
            "evidence_id": f"ev-{idx}",
            "source_url": f"https://source{idx}.example/case",
            "quote_or_evidence": "Visão computacional detecta plantas daninhas em imagens de drones.",
            "source_quality_score": 0.75,
            "evidence_confidence_score": 0.75,
            "confidence": "high",
        }
        for idx in range(3)
    ]
    diagnosis = diagnose_gaps_quantitative(
        run_id="selected-mapping-scope",
        evidence_items=evidence,
        accepted_evidence_items=evidence,
    )
    cv_gap = next(g for g in diagnosis.gaps if g.gap_type == GapType.COMPUTER_VISION_GAP)
    contexts = [
        {
            "context_id": "ctx-tensorrt",
            "chunk_id": "ctx-tensorrt",
            "product": "TensorRT",
            "nvidia_technology": "TensorRT",
            "title": "TensorRT computer vision inference",
            "content": "TensorRT optimizes computer vision inference workloads.",
            "source_id": "nvidia-tensorrt",
            "url": "https://docs.nvidia.example/tensorrt",
            "relevance_score": 0.55,
            "gap_types": ["computer_vision_gap"],
        }
    ]

    result = build_nvidia_technology_mappings(
        run_id="selected-mapping-scope",
        rag_contexts_by_gap={cv_gap.gap_id: contexts, "computer_vision_gap": contexts},
        gap_results=[cv_gap],
        gap_metrics=diagnosis.metrics,
        evidence_items=evidence,
        inventory=_runtime_decision_inventory(),
    )

    mappings = result["nvidia_technology_mappings"]
    assert len(mappings) == len(GAP_TECHNOLOGY_CANDIDATES["computer_vision_gap"])
    assert {item["gap_type"] for item in mappings} == {"computer_vision_gap"}
    supported = [item for item in mappings if item["supporting_rag_context_ids"]]
    assert supported
    assert result["mapping_status"] in {"passed", "needs_review"}
    assert result["mapping_status"] != "needs_more_evidence"
