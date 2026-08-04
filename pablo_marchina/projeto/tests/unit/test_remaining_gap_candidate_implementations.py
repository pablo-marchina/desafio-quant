from __future__ import annotations

from src.rag.evidence_statistical_candidates import (
    EvidenceStatisticalCandidateInput,
    run_statistical_evidence_candidate,
    score_statistical_evidence_output,
)
from src.rag.graph_alternative_candidates import run_graph_alternative_candidate, score_graph_alternative_output
from src.rag.schemas import RetrievedContext


def test_graph_alternative_candidate_runs_local_comparable_implementation() -> None:
    result = run_graph_alternative_candidate(
        candidate_name="Neo4j",
        contexts=[
            RetrievedContext(
                chunk_id="triton_latency",
                source_id="triton",
                title="Triton",
                content="NVIDIA Triton Inference Server improves high latency inference serving.",
                product="Triton Inference Server",
                gap_types=["high_latency"],
                url="https://docs.nvidia.com/triton/",
                relevance_score=0.86,
            )
        ],
        gap_type="high_latency",
        technology="Triton Inference Server",
        alternatives=["Custom server"],
    )

    assert result.implementation_mode == "LOCAL_COMPARABLE_IMPLEMENTATION"
    assert result.lineage_paths
    assert score_graph_alternative_output(result) > 0


def test_statistical_evidence_candidate_uses_product_spike_scoring_shape() -> None:
    item = EvidenceStatisticalCandidateInput(
        required_coverage=0.5,
        provenance_coverage=1.0,
        baseline_confidence=0.86,
        counter_evidence_count=0,
        expected_decision="validate_manually",
    )

    result = run_statistical_evidence_candidate("conformal risk control", item)

    assert result.implementation_mode == "LOCAL_DIRECT_IMPLEMENTATION"
    assert result.required_coverage == 0.5
    assert result.provenance_coverage == 1.0
    assert score_statistical_evidence_output(result, expected_decision=item.expected_decision) > 0
