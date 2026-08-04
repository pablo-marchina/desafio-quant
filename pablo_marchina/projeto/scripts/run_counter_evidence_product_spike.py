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
from src.rag.counter_evidence import retrieve_counter_evidence
from src.rag.schemas import RetrievedContext


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the counter-evidence retrieval product spike benchmark.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--markdown-path", type=Path)
    parser.add_argument("--min-delta", type=float, default=0.12)
    args = parser.parse_args()

    report_path = args.report_path or args.evidence_dir / "counter_evidence_product_spike_report.json"
    markdown_path = args.markdown_path or args.evidence_dir / "counter_evidence_product_spike_report.md"
    report = build_report(min_delta=args.min_delta)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    print(
        "Counter-evidence product spike completed: "
        f"decision={report['decision']}, quality_delta={report['quality_delta']}"
    )
    return 0


def build_report(*, min_delta: float = 0.12) -> dict[str, Any]:
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
        "report_id": "counter_evidence_product_spike_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "PASS",
        "methodology": (
            "Compares baseline high-confidence recommendation output against counter-evidence-aware output. "
            "The benchmark rewards contradiction detection, confidence correction, degraded checks, and missing "
            "evidence prompts. This justifies product spike work, not default runtime adoption."
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
    assessment = retrieve_counter_evidence(
        claim=case["claim"],
        technology=case["technology"],
        gap_type=case["gap_type"],
        baseline_confidence=case["baseline_confidence"],
        contexts=case["contexts"],
    )
    baseline_output = {
        "confidence": case["baseline_confidence"],
        "detected_contradiction_ids": [],
        "degraded_checks": [],
        "missing_evidence": [],
        "uncertainty": round(1.0 - case["baseline_confidence"], 4),
    }
    candidate_output = assessment.model_dump(mode="json")
    baseline_score = _score_output(baseline_output, expected_ids=case["expected_counter_evidence_ids"])
    candidate_score = _score_output(candidate_output, expected_ids=case["expected_counter_evidence_ids"])
    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "quality_delta": round(candidate_score - baseline_score, 4),
        "expected_counter_evidence_ids": case["expected_counter_evidence_ids"],
        "baseline_output": baseline_output,
        "candidate_output": candidate_output,
    }


def _score_output(output: dict[str, Any], *, expected_ids: list[str]) -> float:
    detected = set(output.get("detected_contradiction_ids", []))
    expected = set(expected_ids)
    contradiction_score = len(detected.intersection(expected)) / len(expected) if expected else 1.0
    confidence = float(output.get("adjusted_confidence", output.get("confidence", 1.0)))
    expected_confidence = 0.56 if expected else 0.86
    confidence_score = max(0.0, 1.0 - abs(confidence - expected_confidence))
    degraded_score = 1.0 if output.get("degraded_checks") else (1.0 if not expected else 0.0)
    missing_evidence_score = 1.0 if output.get("missing_evidence") else (1.0 if not expected else 0.0)
    uncertainty = float(output.get("uncertainty", 0.0))
    uncertainty_score = 1.0 if (uncertainty >= 0.35 if expected else uncertainty <= 0.25) else 0.0
    return round(
        contradiction_score * 0.35
        + confidence_score * 0.25
        + degraded_score * 0.15
        + missing_evidence_score * 0.15
        + uncertainty_score * 0.10,
        4,
    )


def _benchmark_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "nim_api_dependency_counter_evidence",
            "description": "NIM recommendation should surface deployment constraints before high confidence.",
            "claim": "NVIDIA NIM is ready to replace third-party inference APIs.",
            "technology": "NVIDIA NIM",
            "gap_type": "external_api_dependency",
            "baseline_confidence": 0.88,
            "expected_counter_evidence_ids": ["nim_private_preview_constraint"],
            "contexts": [
                RetrievedContext(
                    chunk_id="nim_supporting",
                    source_id="nim",
                    title="NVIDIA NIM deployment",
                    content="NVIDIA NIM provides production inference endpoints for deployment control.",
                    product="NVIDIA NIM",
                    gap_types=["external_api_dependency"],
                    url="https://docs.nvidia.com/nim/",
                    relevance_score=0.80,
                ),
                RetrievedContext(
                    chunk_id="nim_private_preview_constraint",
                    source_id="nim_ops",
                    title="NIM operational constraints",
                    content=(
                        "Some model endpoints require manual review and preview access; unsupported regions may "
                        "block production migration."
                    ),
                    product="NVIDIA NIM",
                    gap_types=["external_api_dependency"],
                    url="https://docs.nvidia.com/nim/",
                    relevance_score=0.84,
                ),
            ],
        },
        {
            "case_id": "triton_latency_counter_evidence",
            "description": "Triton recommendation should expose measurement requirements and limitations.",
            "claim": "Triton will reduce p95 latency for the startup workload.",
            "technology": "Triton Inference Server",
            "gap_type": "high_latency",
            "baseline_confidence": 0.86,
            "expected_counter_evidence_ids": ["triton_measurement_requirement"],
            "contexts": [
                RetrievedContext(
                    chunk_id="triton_supporting",
                    source_id="triton",
                    title="Triton Inference Server",
                    content="Triton improves GPU inference serving throughput and latency.",
                    product="Triton Inference Server",
                    gap_types=["high_latency"],
                    url="https://docs.nvidia.com/triton/",
                    relevance_score=0.82,
                ),
                RetrievedContext(
                    chunk_id="triton_measurement_requirement",
                    source_id="triton_perf",
                    title="Triton performance tradeoffs",
                    content=(
                        "Latency gains require workload-specific performance measurement; batching tradeoff may "
                        "increase tail latency for some requests."
                    ),
                    product="Triton Inference Server",
                    gap_types=["high_latency"],
                    url="https://docs.nvidia.com/triton/",
                    relevance_score=0.78,
                ),
            ],
        },
    ]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Counter-Evidence Product Spike Report",
        "",
        f"Generated at: `{report['generated_at']}`",
        f"Decision: `{report['decision']}`",
        f"Baseline score: `{report['baseline_score']}`",
        f"Candidate score: `{report['candidate_score']}`",
        f"Quality delta: `{report['quality_delta']}`",
        "",
        "This report is a product spike benchmark. It does not promote counter-evidence retrieval to default runtime.",
        "",
        "| Case | Baseline | Candidate | Delta | Counter evidence | Adjusted confidence |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for case in report["cases"]:
        output = case["candidate_output"]
        lines.append(
            f"| {_md_cell(case['case_id'])} | {case['baseline_score']} | {case['candidate_score']} | "
            f"{case['quality_delta']} | {len(output['records'])} | {output['adjusted_confidence']} |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
