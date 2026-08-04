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
from src.rag.counter_evidence import CounterEvidenceRecord
from src.rag.evidence_sufficiency import assess_evidence_sufficiency
from src.rag.schemas import RetrievedContext


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the evidence sufficiency product spike benchmark.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--markdown-path", type=Path)
    parser.add_argument("--min-delta", type=float, default=0.08)
    args = parser.parse_args()

    report_path = args.report_path or args.evidence_dir / "evidence_sufficiency_product_spike_report.json"
    markdown_path = args.markdown_path or args.evidence_dir / "evidence_sufficiency_product_spike_report.md"
    report = build_report(min_delta=args.min_delta)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    print(
        "Evidence sufficiency product spike completed: "
        f"decision={report['decision']}, quality_delta={report['quality_delta']}"
    )
    return 0


def build_report(*, min_delta: float = 0.08) -> dict[str, Any]:
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
        "report_id": "evidence_sufficiency_product_spike_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "PASS",
        "methodology": (
            "Compares baseline recommendation output against sufficiency-aware output. The benchmark rewards "
            "required evidence coverage, abstention/manual validation when evidence is missing, confidence "
            "correction, missing-evidence prompts, and degraded checks."
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
    assessment = assess_evidence_sufficiency(
        required_evidence_ids=case["required_evidence_ids"],
        contexts=case["contexts"],
        baseline_confidence=case["baseline_confidence"],
        counter_evidence=case["counter_evidence"],
    )
    baseline_output = {
        "decision": "proceed",
        "required_coverage": case["baseline_required_coverage"],
        "provenance_coverage": case["baseline_provenance_coverage"],
        "adjusted_confidence": case["baseline_confidence"],
        "uncertainty": round(1.0 - case["baseline_confidence"], 4),
        "missing_evidence": [],
        "degraded_checks": [],
    }
    candidate_output = assessment.model_dump(mode="json")
    baseline_score = _score_output(baseline_output, expected_decision=case["expected_decision"])
    candidate_score = _score_output(candidate_output, expected_decision=case["expected_decision"])
    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "quality_delta": round(candidate_score - baseline_score, 4),
        "expected_decision": case["expected_decision"],
        "baseline_output": baseline_output,
        "candidate_output": candidate_output,
    }


def _score_output(output: dict[str, Any], *, expected_decision: str) -> float:
    decision_score = 1.0 if output.get("decision") == expected_decision else 0.0
    coverage = float(output.get("required_coverage", 0.0))
    provenance = float(output.get("provenance_coverage", 0.0))
    confidence = float(output.get("adjusted_confidence", 1.0))
    expected_confidence = 0.82 if expected_decision == "proceed" else 0.48
    if expected_decision == "abstain":
        expected_confidence = 0.35
    confidence_score = max(0.0, 1.0 - abs(confidence - expected_confidence))
    missing_score = 1.0 if output.get("missing_evidence") or expected_decision == "proceed" else 0.0
    degraded_score = 1.0 if output.get("degraded_checks") or expected_decision == "proceed" else 0.0
    return round(
        decision_score * 0.30
        + coverage * 0.20
        + provenance * 0.15
        + confidence_score * 0.15
        + missing_score * 0.10
        + degraded_score * 0.10,
        4,
    )


def _benchmark_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "missing_required_rag_support",
            "description": "Recommendation should validate manually when one required RAG source is missing.",
            "required_evidence_ids": ["triton_latency", "triton_perf_analyzer"],
            "contexts": [
                _context(
                    "triton_latency",
                    "NVIDIA Triton improves inference latency and throughput.",
                    "https://docs.nvidia.com/triton/",
                )
            ],
            "counter_evidence": [],
            "baseline_confidence": 0.86,
            "baseline_required_coverage": 0.50,
            "baseline_provenance_coverage": 1.0,
            "expected_decision": "validate_manually",
        },
        {
            "case_id": "unresolved_counter_evidence_requires_validation",
            "description": "Recommendation should validate manually when unresolved counter-evidence exists.",
            "required_evidence_ids": ["nim_endpoint"],
            "contexts": [
                _context(
                    "nim_endpoint",
                    "NVIDIA NIM provides production inference endpoints.",
                    "https://docs.nvidia.com/nim/",
                )
            ],
            "counter_evidence": [
                CounterEvidenceRecord(
                    evidence_id="nim_preview_constraint",
                    source_id="nim_ops",
                    title="NIM constraints",
                    url="https://docs.nvidia.com/nim/",
                    severity="medium",
                    reason="Source requires manual review.",
                    matched_signals=["manual review"],
                    relevance_score=0.82,
                )
            ],
            "baseline_confidence": 0.88,
            "baseline_required_coverage": 1.0,
            "baseline_provenance_coverage": 1.0,
            "expected_decision": "validate_manually",
        },
        {
            "case_id": "no_required_evidence_abstains",
            "description": "Recommendation should abstain when none of the required evidence is present.",
            "required_evidence_ids": ["guardrails_policy", "guardrails_eval"],
            "contexts": [],
            "counter_evidence": [],
            "baseline_confidence": 0.74,
            "baseline_required_coverage": 0.0,
            "baseline_provenance_coverage": 0.0,
            "expected_decision": "abstain",
        },
    ]


def _context(chunk_id: str, content: str, url: str) -> RetrievedContext:
    return RetrievedContext(
        chunk_id=chunk_id,
        source_id=chunk_id,
        title=chunk_id.replace("_", " ").title(),
        content=content,
        product="NVIDIA",
        gap_types=["high_latency", "external_api_dependency", "agent_governance_gap"],
        url=url,
        relevance_score=0.82,
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Evidence Sufficiency Product Spike Report",
        "",
        f"Generated at: `{report['generated_at']}`",
        f"Decision: `{report['decision']}`",
        f"Baseline score: `{report['baseline_score']}`",
        f"Candidate score: `{report['candidate_score']}`",
        f"Quality delta: `{report['quality_delta']}`",
        "",
        "This report is a product spike benchmark. It does not promote abstention gating to default runtime.",
        "",
        "| Case | Baseline | Candidate | Delta | Expected | Candidate decision |",
        "|---|---:|---:|---:|---|---|",
    ]
    for case in report["cases"]:
        lines.append(
            f"| {_md_cell(case['case_id'])} | {case['baseline_score']} | {case['candidate_score']} | "
            f"{case['quality_delta']} | {_md_cell(case['expected_decision'])} | "
            f"{_md_cell(case['candidate_output']['decision'])} |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
