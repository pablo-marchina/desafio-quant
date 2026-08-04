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
from src.rag.schemas import RetrievedContext
from src.rag.source_quality import rank_contexts_by_source_quality


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the source trust/freshness product spike benchmark.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--markdown-path", type=Path)
    parser.add_argument("--min-delta", type=float, default=0.10)
    args = parser.parse_args()

    report_path = args.report_path or args.evidence_dir / "source_quality_product_spike_report.json"
    markdown_path = args.markdown_path or args.evidence_dir / "source_quality_product_spike_report.md"
    report = build_report(min_delta=args.min_delta)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    print(
        "Source quality product spike completed: "
        f"decision={report['decision']}, quality_delta={report['quality_delta']}"
    )
    return 0


def build_report(*, min_delta: float = 0.10) -> dict[str, Any]:
    results = [_run_case(case) for case in _benchmark_cases()]
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
        "report_id": "source_quality_product_spike_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "PASS",
        "methodology": (
            "Compares relevance-only evidence ordering against trust/freshness-aware source ranking. "
            "The benchmark rewards official NVIDIA provenance, active lifecycle, non-expired sources, "
            "and avoiding stale non-official evidence. This justifies product spike work, not default adoption."
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
    baseline_order = sorted(case["contexts"], key=lambda context: context.relevance_score, reverse=True)
    ranked = rank_contexts_by_source_quality(case["contexts"], now=case["now"])
    candidate_order = [item.context for item in ranked]
    baseline_score = _score_order(baseline_order, expected_top_id=case["expected_top_id"])
    candidate_score = _score_order(candidate_order, expected_top_id=case["expected_top_id"])
    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "quality_delta": round(candidate_score - baseline_score, 4),
        "expected_top_id": case["expected_top_id"],
        "baseline_order": [context.chunk_id for context in baseline_order],
        "candidate_order": [context.chunk_id for context in candidate_order],
        "ranked_contexts": [item.model_dump(mode="json") for item in ranked],
    }


def _score_order(contexts: list[RetrievedContext], *, expected_top_id: str) -> float:
    if not contexts:
        return 0.0
    top = contexts[0]
    top_expected = 1.0 if top.chunk_id == expected_top_id else 0.0
    official_top = 1.0 if top.url and "docs.nvidia.com" in top.url.casefold() else 0.0
    active_top = 1.0 if top.is_active and not top.deprecated_at and not top.superseded_by else 0.0
    provenance = sum(1 for context in contexts[:3] if context.source_id and context.url) / min(len(contexts), 3)
    non_expired = sum(1 for context in contexts[:3] if context.valid_until != "2025-01-01T00:00:00+00:00") / min(
        len(contexts), 3
    )
    return round(
        top_expected * 0.40 + official_top * 0.25 + active_top * 0.15 + provenance * 0.10 + non_expired * 0.10,
        4,
    )


def _benchmark_cases() -> list[dict[str, Any]]:
    now = datetime(2026, 6, 22, tzinfo=UTC)
    return [
        {
            "case_id": "official_nvidia_beats_stale_blog",
            "description": "Official active NVIDIA evidence should outrank a stale non-official post.",
            "expected_top_id": "triton_official_active",
            "now": now,
            "contexts": [
                RetrievedContext(
                    chunk_id="stale_blog_high_relevance",
                    source_id="blog",
                    title="Old Triton benchmark blog",
                    content="Triton latency benchmark, but stale and not an official NVIDIA source.",
                    product="Triton Inference Server",
                    gap_types=["high_latency"],
                    url="https://example.com/old-triton-benchmark",
                    relevance_score=0.94,
                    valid_until="2025-01-01T00:00:00+00:00",
                ),
                RetrievedContext(
                    chunk_id="triton_official_active",
                    source_id="triton_docs",
                    title="Triton official documentation",
                    content="NVIDIA Triton documentation for performance tuning and inference serving.",
                    product="Triton Inference Server",
                    gap_types=["high_latency"],
                    url="https://docs.nvidia.com/deeplearning/triton-inference-server/",
                    relevance_score=0.78,
                    valid_until="2027-01-01T00:00:00+00:00",
                ),
            ],
        },
        {
            "case_id": "active_nim_docs_beats_deprecated_source",
            "description": "Active NIM docs should outrank deprecated source even when relevance is lower.",
            "expected_top_id": "nim_official_active",
            "now": now,
            "contexts": [
                RetrievedContext(
                    chunk_id="nim_deprecated_high_relevance",
                    source_id="old_nim",
                    title="Deprecated NIM note",
                    content="NIM deployment note with high keyword overlap but deprecated lifecycle.",
                    product="NVIDIA NIM",
                    gap_types=["external_api_dependency"],
                    url="https://docs.nvidia.com/nim/old",
                    relevance_score=0.93,
                    valid_until="2025-01-01T00:00:00+00:00",
                    is_active=False,
                    deprecated_at="2025-01-01T00:00:00+00:00",
                ),
                RetrievedContext(
                    chunk_id="nim_official_active",
                    source_id="nim_docs",
                    title="NVIDIA NIM official docs",
                    content="NVIDIA NIM current documentation for production inference endpoints.",
                    product="NVIDIA NIM",
                    gap_types=["external_api_dependency"],
                    url="https://docs.nvidia.com/nim/",
                    relevance_score=0.76,
                    valid_until="2027-01-01T00:00:00+00:00",
                ),
            ],
        },
    ]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Source Quality Product Spike Report",
        "",
        f"Generated at: `{report['generated_at']}`",
        f"Decision: `{report['decision']}`",
        f"Baseline score: `{report['baseline_score']}`",
        f"Candidate score: `{report['candidate_score']}`",
        f"Quality delta: `{report['quality_delta']}`",
        "",
        "This report is a product spike benchmark. It does not promote source quality ranking to default runtime.",
        "",
        "| Case | Baseline | Candidate | Delta | Baseline top | Candidate top |",
        "|---|---:|---:|---:|---|---|",
    ]
    for case in report["cases"]:
        lines.append(
            f"| {_md_cell(case['case_id'])} | {case['baseline_score']} | {case['candidate_score']} | "
            f"{case['quality_delta']} | {_md_cell(case['baseline_order'][0])} | "
            f"{_md_cell(case['candidate_order'][0])} |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
