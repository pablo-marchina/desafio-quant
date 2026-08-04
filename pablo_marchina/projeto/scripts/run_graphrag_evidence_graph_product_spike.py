#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json
from src.rag.evidence_graph import EvidenceGraphConfig, build_evidence_graph, graph_lineage_summary
from src.rag.schemas import RetrievedContext


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the GraphRAG evidence graph product spike benchmark.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--markdown-path", type=Path)
    parser.add_argument("--min-delta", type=float, default=0.20)
    args = parser.parse_args()

    report_path = args.report_path or args.evidence_dir / "graphrag_evidence_graph_product_spike_report.json"
    markdown_path = args.markdown_path or args.evidence_dir / "graphrag_evidence_graph_product_spike_report.md"
    report = build_report(min_delta=args.min_delta)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    print(
        "GraphRAG evidence graph product spike completed: "
        f"decision={report['decision']}, quality_delta={report['quality_delta']}"
    )
    return 0


def build_report(*, min_delta: float = 0.20) -> dict[str, Any]:
    cases = _benchmark_cases()
    results = [_run_case(case) for case in cases]
    baseline = _mean([result["baseline_score"] for result in results])
    candidate = _mean([result["candidate_score"] for result in results])
    delta = candidate - baseline
    regressions = [result for result in results if result["quality_delta"] < 0]
    decision = (
        "PROMOTE_TO_PRODUCT_SPIKE"
        if delta >= min_delta and not regressions
        else ("BLOCKED_BY_REGRESSION" if regressions else "REJECT_NO_PRODUCT_SPIKE_LIFT")
    )
    return {
        "report_id": "graphrag_evidence_graph_product_spike_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "PASS",
        "methodology": (
            "Compares baseline evidence summaries against deterministic source-gap-technology evidence graphs. "
            "This justifies product spike work, not default runtime adoption."
        ),
        "decision": decision,
        "baseline_score": round(baseline, 4),
        "candidate_score": round(candidate, 4),
        "quality_delta": round(delta, 4),
        "min_delta": min_delta,
        "regression_count": len(regressions),
        "case_count": len(results),
        "cases": results,
    }


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    graph = build_evidence_graph(
        contexts=case["contexts"],
        gap_type=case["gap_type"],
        technology=case["technology"],
        alternatives=case["alternatives"],
        config=EvidenceGraphConfig(),
    )
    baseline_output = _baseline_output(case)
    candidate_output = {
        "lineage_paths": graph.lineage_paths,
        "provenance_coverage": graph.metrics["provenance_coverage"],
        "alternatives_lost": graph.alternatives_lost,
        "graph_completeness_score": graph.metrics["graph_completeness_score"],
        "lineage_summary": graph_lineage_summary(graph),
    }
    baseline_score = _score_output(baseline_output)
    candidate_score = _score_output(candidate_output)
    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "quality_delta": round(candidate_score - baseline_score, 4),
        "baseline_output": baseline_output,
        "candidate_output": candidate_output,
        "graph": graph.model_dump(mode="json"),
    }


def _baseline_output(case: dict[str, Any]) -> dict[str, Any]:
    contexts = case["contexts"]
    return {
        "source_ids": [context.source_id for context in contexts if context.source_id],
        "gap_type": case["gap_type"],
        "technology": case["technology"],
        "lineage_paths": [],
        "provenance_coverage": sum(1 for context in contexts if context.source_id and context.url) / len(contexts),
        "alternatives_lost": [],
        "graph_completeness_score": 0.0,
    }


def _score_output(output: dict[str, Any]) -> float:
    lineage_score = 1.0 if output.get("lineage_paths") else 0.0
    provenance_score = float(output.get("provenance_coverage", 0.0))
    alternatives_score = 1.0 if output.get("alternatives_lost") else 0.0
    completeness_score = float(output.get("graph_completeness_score", 0.0))
    explicit_summary_score = 1.0 if output.get("lineage_summary") else 0.0
    return round(
        lineage_score * 0.35
        + provenance_score * 0.20
        + alternatives_score * 0.20
        + completeness_score * 0.20
        + explicit_summary_score * 0.05,
        4,
    )


def _benchmark_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "latency_triton_lineage",
            "description": (
                "Latency recommendation should expose source-gap-technology lineage and losing alternatives."
            ),
            "gap_type": "high_latency",
            "technology": "Triton Inference Server",
            "alternatives": ["Generic autoscaling", "Custom model server"],
            "contexts": [
                RetrievedContext(
                    chunk_id="triton_latency",
                    source_id="triton",
                    title="Triton Inference Server",
                    content="NVIDIA Triton Inference Server improves GPU inference latency and throughput.",
                    product="Triton Inference Server",
                    gap_types=["high_latency", "high_inference_cost"],
                    url="https://docs.nvidia.com/triton/",
                    relevance_score=0.86,
                ),
                RetrievedContext(
                    chunk_id="triton_perf_analyzer",
                    source_id="triton_performance",
                    title="Triton Performance Analyzer",
                    content="Performance Analyzer measures inference latency, throughput, and model serving tradeoffs.",
                    product="Triton Inference Server",
                    gap_types=["high_latency"],
                    url="https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/perf_analyzer/",
                    relevance_score=0.78,
                ),
            ],
        },
        {
            "case_id": "api_dependency_nim_lineage",
            "description": "External API dependency recommendation should show NIM evidence and alternatives lost.",
            "gap_type": "external_api_dependency",
            "technology": "NVIDIA NIM",
            "alternatives": ["Third-party hosted endpoint", "Unmanaged OSS endpoint"],
            "contexts": [
                RetrievedContext(
                    chunk_id="nim_endpoint",
                    source_id="nim",
                    title="NVIDIA NIM",
                    content="NVIDIA NIM provides production inference endpoints and deployment control.",
                    product="NVIDIA NIM",
                    gap_types=["external_api_dependency", "high_inference_cost"],
                    url="https://docs.nvidia.com/nim/",
                    relevance_score=0.83,
                ),
                RetrievedContext(
                    chunk_id="nim_observability",
                    source_id="nim_operations",
                    title="NVIDIA NIM Operations",
                    content="NIM deployment guidance supports reliable endpoint operations for production AI systems.",
                    product="NVIDIA NIM",
                    gap_types=["external_api_dependency", "observability_gap"],
                    url="https://docs.nvidia.com/nim/",
                    relevance_score=0.74,
                ),
            ],
        },
    ]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# GraphRAG Evidence Graph Product Spike Report",
        "",
        f"Generated at: `{report['generated_at']}`",
        f"Decision: `{report['decision']}`",
        f"Baseline score: `{report['baseline_score']}`",
        f"Candidate score: `{report['candidate_score']}`",
        f"Quality delta: `{report['quality_delta']}`",
        "",
        "This report is a product spike benchmark. It does not promote GraphRAG evidence graphs to default runtime.",
        "",
        "| Case | Baseline | Candidate | Delta | Lineage paths | Alternatives lost |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for case in report["cases"]:
        graph_metrics = case["graph"]["metrics"]
        lines.append(
            f"| {_md_cell(case['case_id'])} | {case['baseline_score']} | {case['candidate_score']} | "
            f"{case['quality_delta']} | {graph_metrics['lineage_path_count']} | "
            f"{graph_metrics['alternatives_lost_count']} |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
