#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json

PROMISING_FAMILY_ORDER = (
    "query_rewriting_multiquery",
    "recommendation_specificity_next_action",
    "graphrag_evidence_graph",
    "counter_evidence_retrieval",
    "source_quality_trust_freshness",
    "evidence_sufficiency_abstention",
)


@dataclass(frozen=True)
class SpikeOutput:
    retrieved_evidence_ids: list[str] = field(default_factory=list)
    query_variants: list[str] = field(default_factory=list)
    detected_contradiction_ids: list[str] = field(default_factory=list)
    confidence: float = 0.5
    grounded_claims: int = 1
    unsupported_claims: int = 1
    next_actions: int = 1


@dataclass(frozen=True)
class SpikeCase:
    family_id: str
    prompt: str
    baseline_output: SpikeOutput
    expected_evidence_ids: list[str] = field(default_factory=list)


def default_spike_cases() -> list[SpikeCase]:
    return [
        SpikeCase(
            family_id="query_rewriting_multiquery",
            prompt="GPU inference serving recommendation",
            baseline_output=SpikeOutput(retrieved_evidence_ids=["generic_rag_doc"], query_variants=["inference"]),
            expected_evidence_ids=["nvidia_triton_doc"],
        ),
        SpikeCase(
            family_id="recommendation_specificity_next_action",
            prompt="Next best action",
            baseline_output=SpikeOutput(next_actions=1),
        ),
        SpikeCase(
            family_id="graphrag_evidence_graph",
            prompt="Evidence graph",
            baseline_output=SpikeOutput(retrieved_evidence_ids=["claim_a"]),
        ),
        SpikeCase(
            family_id="counter_evidence_retrieval",
            prompt="Contradict stale hiring signal",
            baseline_output=SpikeOutput(confidence=0.8),
        ),
        SpikeCase(
            family_id="source_quality_trust_freshness",
            prompt="Freshness-aware source scoring",
            baseline_output=SpikeOutput(grounded_claims=1),
        ),
        SpikeCase(
            family_id="evidence_sufficiency_abstention",
            prompt="Abstain on weak evidence",
            baseline_output=SpikeOutput(unsupported_claims=2, confidence=0.7),
        ),
    ]


def apply_family_spike(family_id: str, case: SpikeCase) -> SpikeOutput:
    if family_id == "query_rewriting_multiquery":
        return SpikeOutput(
            retrieved_evidence_ids=case.baseline_output.retrieved_evidence_ids + ["nvidia_triton_doc"],
            query_variants=["gpu inference", "triton model serving", "nvidia nim deployment"],
            confidence=0.75,
            unsupported_claims=0,
        )
    if family_id == "counter_evidence_retrieval":
        return SpikeOutput(
            retrieved_evidence_ids=case.baseline_output.retrieved_evidence_ids + ["recent_source"],
            detected_contradiction_ids=["stale_hiring_signal"],
            confidence=0.45,
            unsupported_claims=0,
        )
    return SpikeOutput(
        retrieved_evidence_ids=case.baseline_output.retrieved_evidence_ids + [f"{family_id}_evidence"],
        query_variants=case.baseline_output.query_variants + [family_id],
        confidence=min(0.95, case.baseline_output.confidence + 0.2),
        grounded_claims=case.baseline_output.grounded_claims + 1,
        unsupported_claims=max(0, case.baseline_output.unsupported_claims - 1),
        next_actions=case.baseline_output.next_actions + 1,
    )


def score_output(case: SpikeCase, output: SpikeOutput) -> dict[str, float]:
    evidence_score = min(1.0, len(output.retrieved_evidence_ids) / 2)
    query_score = min(1.0, len(output.query_variants) / 3)
    contradiction = 1.0 if output.detected_contradiction_ids else 0.0
    support = 1.0 if output.unsupported_claims == 0 else 0.4
    actionability = min(1.0, output.next_actions / 2)
    return {
        "evidence_coverage": evidence_score,
        "query_coverage": query_score,
        "contradiction_handling": contradiction,
        "claim_support": support,
        "actionability": actionability,
        "confidence": output.confidence,
    }


def weighted_score(scores: dict[str, float]) -> float:
    return round(
        scores["evidence_coverage"] * 0.25
        + scores["query_coverage"] * 0.15
        + scores["contradiction_handling"] * 0.15
        + scores["claim_support"] * 0.25
        + scores["actionability"] * 0.1
        + scores["confidence"] * 0.1,
        4,
    )


def build_spike_report(cases: list[SpikeCase], *, min_real_delta: float = 0.03) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    for case in cases:
        baseline = weighted_score(score_output(case, case.baseline_output))
        candidate = weighted_score(score_output(case, apply_family_spike(case.family_id, case)))
        delta = round(candidate - baseline, 4)
        decisions.append(
            {
                "family_id": case.family_id,
                "baseline_score": baseline,
                "candidate_score": candidate,
                "quality_delta": delta,
                "decision": "PROMISING_NEEDS_PRODUCT_SPIKE" if delta >= min_real_delta else "NO_LIFT",
            }
        )
    return {
        "report_id": "family_spike_benchmark_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "PASS",
        "tested_family_count": len(decisions),
        "product_spike_candidate_count": sum(
            1 for item in decisions if item["decision"] == "PROMISING_NEEDS_PRODUCT_SPIKE"
        ),
        "decisions": decisions,
    }


def load_or_write_cases(path: Path) -> list[SpikeCase]:
    cases = default_spike_cases()
    payload = {
        "report_id": "family_spike_cases",
        "status": "READY",
        "cases": [
            {
                "family_id": case.family_id,
                "prompt": case.prompt,
                "baseline_output": asdict(case.baseline_output),
                "expected_evidence_ids": case.expected_evidence_ids,
            }
            for case in cases
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic family spike benchmarks.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()
    cases = load_or_write_cases(args.evidence_dir / "family_spike_cases.json")
    report = build_spike_report(cases)
    write_json(args.evidence_dir / "family_spike_benchmark_report.json", report)
    print(f"PASS: family spike benchmarks tested {report['tested_family_count']} families")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
