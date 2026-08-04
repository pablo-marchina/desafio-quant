from __future__ import annotations

from src.diagnosis.gap_diagnosis_scoring import diagnose_gaps_quantitative
from src.diagnosis.schemas import GapType
from src.rag.rag_service_factory import _rerank_with_configured_provider
from src.rag.schemas import RetrievalQuery
from src.recommendation.nvidia_technology_mapping import build_nvidia_technology_mappings


def test_local_cross_encoder_handles_an_empty_candidate_batch(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("RERANKER_PROVIDER", "local_cross_encoder")

    ranked, metrics = _rerank_with_configured_provider(
        [],
        RetrievalQuery(gap_type="computer_vision_gap", technology="TensorRT"),
    )

    assert ranked == []
    assert metrics["called"] is False
    assert metrics["input_count"] == 0
    assert metrics["reason"] == "no_contexts_to_rerank"


def test_mapping_uses_gap_evidence_and_runtime_gap_id_context_bucket() -> None:
    evidence = [
        {
            "evidence_id": f"ev-{idx}",
            "source_url": f"https://source{idx}.example/case",
            "quote_or_evidence": "Visão computacional detecta plantas daninhas em imagens de drones.",
            "source_quality_score": 0.9,
            "evidence_confidence_score": 0.9,
            "confidence": "high",
        }
        for idx in range(3)
    ]
    diagnosis = diagnose_gaps_quantitative(
        run_id="mapping-provenance-diagnosis",
        evidence_items=evidence,
        accepted_evidence_items=evidence,
    )
    cv_gap = next(g for g in diagnosis.gaps if g.gap_type == GapType.COMPUTER_VISION_GAP)

    contexts = [
        {
            "context_id": f"ctx-{idx}",
            "chunk_id": f"ctx-{idx}",
            "product": "TensorRT",
            "nvidia_technology": "TensorRT",
            "title": "TensorRT inference optimization",
            "content": "TensorRT optimizes computer vision inference workloads.",
            "source_id": f"nvidia-source-{idx}",
            "url": f"https://docs.nvidia.example/tensorrt/{idx}",
            "relevance_score": 0.95,
            "gap_types": ["computer_vision_gap"],
        }
        for idx in range(2)
    ]

    result = build_nvidia_technology_mappings(
        run_id="mapping-provenance",
        rag_contexts_by_gap={cv_gap.gap_id: contexts},
        gap_results=[cv_gap],
        gap_metrics=diagnosis.metrics,
        evidence_items=evidence,
    )
    tensorrt = next(
        item
        for item in result["nvidia_technology_mappings"]
        if item["gap_type"] == "computer_vision_gap" and item["nvidia_technology"] == "TensorRT"
    )

    assert tensorrt["supporting_rag_context_ids"] == ["ctx-0", "ctx-1"]
    assert tensorrt["supporting_evidence_ids"] == ["ev-0", "ev-1", "ev-2"]
    assert "TensorRT" not in " ".join(item["quote_or_evidence"] for item in evidence)
