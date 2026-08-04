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

from src.extraction.schemas import ConfidenceLevel, ImplementationComplexity, RecommendationPriority, TechnicalGap
from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json
from src.recommendation.next_action_enrichment import (
    NextActionEnrichmentConfig,
    enrich_next_action,
    score_next_action,
)
from src.recommendation.schemas import PerGapRecommendation, RecommendedNextAction


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the next-action enrichment product spike benchmark.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--markdown-path", type=Path)
    parser.add_argument("--min-delta", type=float, default=0.35)
    args = parser.parse_args()

    report_path = args.report_path or args.evidence_dir / "next_action_enrichment_product_spike_report.json"
    markdown_path = args.markdown_path or args.evidence_dir / "next_action_enrichment_product_spike_report.md"
    report = build_report(min_delta=args.min_delta)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    print(
        "Next-action enrichment product spike completed: "
        f"decision={report['decision']}, quality_delta={report['quality_delta']}"
    )
    return 0


def build_report(*, min_delta: float = 0.35) -> dict[str, Any]:
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
        "report_id": "next_action_enrichment_product_spike_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "PASS",
        "methodology": (
            "Compares generic recommendation next actions against deterministic enriched next actions. "
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
    recommendation = case["recommendation"]
    enriched = enrich_next_action(recommendation, NextActionEnrichmentConfig())
    baseline_score = score_next_action(recommendation.next_action_for_nvidia_team)
    candidate_score = score_next_action(recommendation.next_action_for_nvidia_team, enriched)
    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "quality_delta": round(candidate_score - baseline_score, 4),
        "baseline_next_action": recommendation.next_action_for_nvidia_team,
        "enriched_next_action": enriched.model_dump(mode="json") if enriched else None,
    }


def _benchmark_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "latency_action_to_measurable_experiment",
            "description": "Generic latency recommendation should become a measurable Triton experiment.",
            "recommendation": _recommendation(
                gap=TechnicalGap.HIGH_LATENCY,
                technology="Triton Inference Server",
                action_text="Contact startup to discuss Triton adoption.",
            ),
        },
        {
            "case_id": "api_dependency_action_to_nim_experiment",
            "description": "External API dependency recommendation should define NIM validation metrics.",
            "recommendation": _recommendation(
                gap=TechnicalGap.EXTERNAL_API_DEPENDENCY,
                technology="NVIDIA NIM",
                action_text="Schedule technical discussion about NVIDIA NIM.",
            ),
        },
        {
            "case_id": "governance_action_to_guardrails_experiment",
            "description": "Agent governance recommendation should include violation-rate measurement.",
            "recommendation": _recommendation(
                gap=TechnicalGap.AGENT_GOVERNANCE_GAP,
                technology="NeMo Guardrails",
                action_text="Run a guardrails workshop.",
            ),
        },
    ]


def _recommendation(gap: TechnicalGap, technology: str, action_text: str) -> PerGapRecommendation:
    return PerGapRecommendation(
        diagnosed_gap=gap,
        detected=True,
        recommended_nvidia_technologies=[technology],
        technical_justification="RAG-supported technical fit.",
        business_justification="Improves activation quality.",
        priority=RecommendationPriority.HIGH,
        implementation_complexity=ImplementationComplexity.MEDIUM,
        action=RecommendedNextAction.APPROACH_NOW,
        next_action_for_nvidia_team=action_text,
        confidence=ConfidenceLevel.HIGH,
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Next-Action Enrichment Product Spike Report",
        "",
        f"Generated at: `{report['generated_at']}`",
        f"Decision: `{report['decision']}`",
        f"Baseline score: `{report['baseline_score']}`",
        f"Candidate score: `{report['candidate_score']}`",
        f"Quality delta: `{report['quality_delta']}`",
        "",
        "This report is a product spike benchmark. It does not promote enriched next actions to default runtime.",
        "",
        "| Case | Baseline | Candidate | Delta | Technology |",
        "|---|---:|---:|---:|---|",
    ]
    for case in report["cases"]:
        enriched = case["enriched_next_action"] or {}
        lines.append(
            f"| {_md_cell(case['case_id'])} | {case['baseline_score']} | {case['candidate_score']} | "
            f"{case['quality_delta']} | {_md_cell(str(enriched.get('technology', '')))} |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
