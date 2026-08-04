from __future__ import annotations

from scripts import run_graphrag_evidence_graph_product_spike
from src.rag.evidence_graph import EvidenceGraphConfig, build_evidence_graph, graph_lineage_summary
from src.rag.schemas import RetrievedContext


def _contexts() -> list[RetrievedContext]:
    return [
        RetrievedContext(
            chunk_id="triton_latency",
            source_id="triton",
            title="Triton Inference Server",
            content="NVIDIA Triton Inference Server improves GPU inference latency and throughput.",
            product="Triton Inference Server",
            gap_types=["high_latency"],
            url="https://docs.nvidia.com/triton/",
            relevance_score=0.88,
        ),
        RetrievedContext(
            chunk_id="generic",
            source_id="generic",
            title="Generic Serving",
            content="Generic serving overview.",
            product="Generic AI",
            gap_types=["observability_gap"],
            url="https://example.com/generic",
            relevance_score=0.20,
        ),
    ]


def test_evidence_graph_builds_source_gap_technology_lineage() -> None:
    graph = build_evidence_graph(
        contexts=_contexts(),
        gap_type="high_latency",
        technology="Triton Inference Server",
        alternatives=["Generic Serving"],
        config=EvidenceGraphConfig(),
    )

    assert graph.metrics["lineage_path_count"] == 1
    assert graph.metrics["graph_completeness_score"] >= 0.75
    assert any(edge.relation == "maps_gap_to_technology" for edge in graph.edges)
    assert "lineage path" in graph_lineage_summary(graph)


def test_evidence_graph_records_alternatives_lost_with_evidence_ids() -> None:
    graph = build_evidence_graph(
        contexts=_contexts(),
        gap_type="high_latency",
        technology="Triton Inference Server",
        alternatives=["Custom model server"],
        config=EvidenceGraphConfig(),
    )

    assert graph.alternatives_lost
    assert graph.alternatives_lost[0]["lost_to"] == "Triton Inference Server"
    assert graph.alternatives_lost[0]["evidence_ids"] == ["triton_latency"]


def test_evidence_graph_drops_unprovenanced_contexts_when_required() -> None:
    context = RetrievedContext(
        chunk_id="no_url",
        source_id="source",
        title="No URL",
        content="NVIDIA NIM supports external api dependency.",
        product="NVIDIA NIM",
        gap_types=["external_api_dependency"],
        relevance_score=0.90,
    )

    graph = build_evidence_graph(
        contexts=[context],
        gap_type="external_api_dependency",
        technology="NVIDIA NIM",
        config=EvidenceGraphConfig(require_provenance=True),
    )

    assert graph.metrics["source_count"] == 0
    assert "contexts_without_required_provenance_dropped" in graph.warnings


def test_graphrag_evidence_graph_product_spike_report_promotes_product_spike() -> None:
    report = run_graphrag_evidence_graph_product_spike.build_report(min_delta=0.20)

    assert report["decision"] == "PROMOTE_TO_PRODUCT_SPIKE"
    assert report["quality_delta"] >= 0.20
    assert report["regression_count"] == 0
    assert report["case_count"] == 2
