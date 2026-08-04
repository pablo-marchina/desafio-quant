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
from src.rag.query_rewriting import QueryRewriteConfig, build_query_variants, retrieve_multi_query
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RagChunk, RetrievalQuery, RetrievedContext


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the query rewriting product spike benchmark.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--markdown-path", type=Path)
    parser.add_argument("--min-delta", type=float, default=0.20)
    args = parser.parse_args()

    report_path = args.report_path or args.evidence_dir / "query_rewriting_product_spike_report.json"
    markdown_path = args.markdown_path or args.evidence_dir / "query_rewriting_product_spike_report.md"
    report = build_report(min_delta=args.min_delta)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    print(
        "Query rewriting product spike completed: "
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
        "report_id": "query_rewriting_product_spike_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "PASS",
        "methodology": (
            "Compares baseline lexical retrieval against deterministic multi-query rewriting on local product-like "
            "cases. This justifies product spike work, not default runtime adoption."
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
    index = ChunkIndex(case["chunks"])
    query = case["query"]
    config = QueryRewriteConfig(max_variants=4)
    baseline = index.retrieve(query, top_k=case["top_k"])
    candidate = retrieve_multi_query(index, query, top_k=case["top_k"], config=config)
    baseline_score = _score_retrieval(baseline, case["expected_chunk_ids"])
    candidate_score = _score_retrieval(candidate, case["expected_chunk_ids"])
    variants = build_query_variants(query, config)
    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "quality_delta": round(candidate_score - baseline_score, 4),
        "baseline_chunk_ids": [context.chunk_id for context in baseline],
        "candidate_chunk_ids": [context.chunk_id for context in candidate],
        "query_variants": [variant.model_dump(mode="json") for variant in variants],
        "expected_chunk_ids": case["expected_chunk_ids"],
    }


def _score_retrieval(contexts: list[RetrievedContext], expected_chunk_ids: list[str]) -> float:
    if not expected_chunk_ids:
        return 1.0
    retrieved = [context.chunk_id for context in contexts]
    expected = set(expected_chunk_ids)
    coverage = len(expected.intersection(retrieved)) / len(expected)
    top_1 = 1.0 if retrieved and retrieved[0] in expected else 0.0
    provenance = (
        sum(1 for context in contexts if context.source_id and context.url) / len(contexts) if contexts else 0.0
    )
    return round((coverage * 0.55) + (top_1 * 0.30) + (provenance * 0.15), 4)


def _benchmark_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "business_vocab_to_triton",
            "description": "Business vocabulary should recover Triton inference evidence.",
            "query": RetrievalQuery(keywords=["scale", "delivery", "enterprise"]),
            "expected_chunk_ids": ["triton_inference"],
            "top_k": 3,
            "chunks": _chunks(),
        },
        {
            "case_id": "business_vocab_to_nim",
            "description": "AI delivery vocabulary should recover NVIDIA NIM evidence.",
            "query": RetrievalQuery(keywords=["ai", "customers", "delivery"]),
            "expected_chunk_ids": ["nim_endpoint"],
            "top_k": 3,
            "chunks": _chunks(),
        },
    ]


def _chunks() -> list[RagChunk]:
    return [
        RagChunk(
            chunk_id="triton_inference",
            source_id="triton",
            title="Triton Inference Server",
            content="NVIDIA Triton Inference Server improves GPU inference model serving latency and throughput.",
            product="Triton Inference Server",
            gap_types=["high_latency", "high_inference_cost"],
            url="https://docs.nvidia.com/triton/",
        ),
        RagChunk(
            chunk_id="nim_endpoint",
            source_id="nim",
            title="NVIDIA NIM",
            content="NVIDIA NIM provides production inference endpoints for AI model deployment.",
            product="NVIDIA NIM",
            gap_types=["external_api_dependency", "high_inference_cost"],
            url="https://docs.nvidia.com/nim/",
        ),
        RagChunk(
            chunk_id="generic_ai",
            source_id="generic",
            title="Generic AI Overview",
            content=(
                "Generic AI platforms can support enterprise analytics without specific NVIDIA deployment guidance."
            ),
            product="Generic AI",
            gap_types=["observability_gap"],
            url="https://example.com/generic-ai",
        ),
    ]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Query Rewriting Product Spike Report",
        "",
        f"Generated at: `{report['generated_at']}`",
        f"Decision: `{report['decision']}`",
        f"Baseline score: `{report['baseline_score']}`",
        f"Candidate score: `{report['candidate_score']}`",
        f"Quality delta: `{report['quality_delta']}`",
        "",
        "This report is a product spike benchmark. It does not promote query rewriting to default runtime behavior.",
        "",
        "| Case | Baseline | Candidate | Delta | Candidate chunks |",
        "|---|---:|---:|---:|---|",
    ]
    for case in report["cases"]:
        lines.append(
            f"| {_md_cell(case['case_id'])} | {case['baseline_score']} | {case['candidate_score']} | "
            f"{case['quality_delta']} | {_md_cell(', '.join(case['candidate_chunk_ids']))} |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
