#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pydantic import BaseModel, Field, field_validator

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json

QUALITY_WEIGHTS: dict[str, float] = {
    "evidence_sufficiency": 0.15,
    "unsupported_claim_control": 0.11,
    "source_trust_freshness": 0.09,
    "contradiction_handling": 0.09,
    "recommendation_specificity": 0.11,
    "next_action_quality": 0.09,
    "uncertainty_calibration": 0.08,
    "lineage_traceability": 0.07,
    "alternatives_lost_rationale": 0.05,
    "robustness_to_query_variance": 0.07,
    "evaluator_auditability": 0.06,
    "operational_efficiency": 0.03,
}


class DiagnosticCase(BaseModel):
    case_id: str
    name: str
    description: str
    improvement_opportunity: str
    baseline_scores: dict[str, float]
    target_families: list[str]
    expected_user_value: str

    @field_validator("baseline_scores")
    @classmethod
    def validate_scores(cls, value: dict[str, float]) -> dict[str, float]:
        missing = set(QUALITY_WEIGHTS) - set(value)
        if missing:
            raise ValueError(f"Missing quality scores: {sorted(missing)}")
        for metric, score in value.items():
            if metric not in QUALITY_WEIGHTS:
                raise ValueError(f"Unknown quality metric: {metric}")
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"Quality score must be between 0 and 1 for {metric}")
        return value


class OracleIntervention(BaseModel):
    family_id: str
    display_name: str
    target_metrics: dict[str, float]
    technology_examples: list[str]
    spike_shape: str

    @field_validator("target_metrics")
    @classmethod
    def validate_target_metrics(cls, value: dict[str, float]) -> dict[str, float]:
        for metric, lift in value.items():
            if metric not in QUALITY_WEIGHTS:
                raise ValueError(f"Unknown quality metric: {metric}")
            if not 0.0 <= lift <= 1.0:
                raise ValueError(f"Oracle lift must be between 0 and 1 for {metric}")
        return value


class FamilyDecision(BaseModel):
    family_id: str
    display_name: str
    decision: str
    baseline_quality_score: float
    oracle_quality_score: float
    quality_delta: float
    affected_case_quality_delta: float
    affected_case_count: int
    affected_cases: list[str]
    residual_headroom: float
    technology_examples: list[str]
    matching_candidates: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str
    next_step: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run diagnostic output-quality triage before implementing technology spikes."
    )
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--cases-path", type=Path)
    parser.add_argument("--queue-path", type=Path)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--markdown-path", type=Path)
    parser.add_argument("--min-oracle-delta", type=float, default=0.025)
    parser.add_argument("--max-spike-candidates", type=int, default=4)
    args = parser.parse_args()

    evidence_dir = args.evidence_dir
    cases_path = args.cases_path or evidence_dir / "diagnostic_eval_cases.json"
    queue_path = args.queue_path or evidence_dir / "ranked_value_candidate_queue.json"
    report_path = args.report_path or evidence_dir / "diagnostic_value_triage_report.json"
    markdown_path = args.markdown_path or evidence_dir / "diagnostic_value_triage_report.md"

    cases = load_or_write_cases(cases_path)
    ranked_candidates = _load_ranked_candidates(queue_path)
    report = build_diagnostic_report(
        cases,
        default_oracle_interventions(),
        ranked_candidates=ranked_candidates,
        min_oracle_delta=args.min_oracle_delta,
        max_spike_candidates=args.max_spike_candidates,
    )
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    print(
        "Diagnostic value triage completed: "
        f"{report['spike_candidate_count']} spike candidates, "
        f"top_family={report['top_spike_family'] or 'none'}"
    )
    return 0


def load_or_write_cases(path: Path) -> list[DiagnosticCase]:
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_cases = payload.get("cases", payload) if isinstance(payload, dict) else payload
        if isinstance(raw_cases, list) and raw_cases:
            return [DiagnosticCase.model_validate(item) for item in raw_cases]
    cases = default_diagnostic_cases()
    write_json(
        path,
        {
            "report_id": "diagnostic_eval_cases",
            "generated_at": datetime.now(UTC).isoformat(),
            "purpose": (
                "Cases expose marginal system-value opportunity before any technology family is implemented in product."
            ),
            "quality_weights": QUALITY_WEIGHTS,
            "cases": [case.model_dump(mode="json") for case in cases],
        },
    )
    return cases


def build_diagnostic_report(
    cases: list[DiagnosticCase],
    interventions: list[OracleIntervention],
    *,
    ranked_candidates: list[dict[str, Any]] | None = None,
    min_oracle_delta: float = 0.025,
    max_spike_candidates: int = 4,
) -> dict[str, Any]:
    baseline_quality = _average_case_quality(cases)
    candidates = ranked_candidates or []
    decisions = [
        _family_decision(
            intervention,
            cases,
            baseline_quality=baseline_quality,
            ranked_candidates=candidates,
            min_oracle_delta=min_oracle_delta,
        )
        for intervention in interventions
    ]
    decisions.sort(
        key=lambda decision: (-decision.affected_case_quality_delta, -decision.quality_delta, decision.family_id)
    )
    spike_candidates = [decision for decision in decisions if decision.decision == "SPIKE_CANDIDATE"]
    recommended_spikes = spike_candidates[:max_spike_candidates]
    return {
        "report_id": "diagnostic_value_triage_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "methodology": (
            "This is a pre-implementation oracle triage. It measures marginal system-value lift across output "
            "quality, robustness, auditability, and efficiency, then estimates which technology families deserve a "
            "spike. It is not a runtime adoption benchmark."
        ),
        "quality_weights": QUALITY_WEIGHTS,
        "case_count": len(cases),
        "baseline_quality_score": round(baseline_quality, 4),
        "min_oracle_delta": min_oracle_delta,
        "spike_candidate_count": len(spike_candidates),
        "top_spike_family": recommended_spikes[0].family_id if recommended_spikes else "",
        "recommended_spikes": [decision.model_dump(mode="json") for decision in recommended_spikes],
        "family_decisions": [decision.model_dump(mode="json") for decision in decisions],
        "case_scores": [
            {
                "case_id": case.case_id,
                "name": case.name,
                "baseline_quality_score": round(score_case(case.baseline_scores), 4),
                "target_families": case.target_families,
                "improvement_opportunity": case.improvement_opportunity,
            }
            for case in cases
        ],
    }


def _family_decision(
    intervention: OracleIntervention,
    cases: list[DiagnosticCase],
    *,
    baseline_quality: float,
    ranked_candidates: list[dict[str, Any]],
    min_oracle_delta: float,
) -> FamilyDecision:
    affected = [case for case in cases if intervention.family_id in case.target_families]
    oracle_scores = [
        score_case(_apply_oracle(case.baseline_scores, intervention if case in affected else None)) for case in cases
    ]
    oracle_quality = sum(oracle_scores) / len(oracle_scores) if oracle_scores else 0.0
    delta = oracle_quality - baseline_quality
    affected_case_delta = _affected_case_delta(affected, intervention)
    residual_headroom = max(0.0, 1.0 - oracle_quality)
    matching_candidates = _matching_candidates(intervention, ranked_candidates)
    if not affected:
        decision = "NOT_APPLICABLE"
        rationale = "No diagnostic case currently measures marginal value for this improvement family."
        next_step = "Do not implement; add a diagnostic value case first if this family becomes relevant."
    elif affected_case_delta >= min_oracle_delta:
        decision = "SPIKE_CANDIDATE"
        rationale = "Oracle lift shows measurable marginal system-value for this family."
        next_step = (
            "Build the smallest disposable spike that targets the affected diagnostic cases, then run a real "
            "quality benchmark before product promotion."
        )
    else:
        decision = "NO_MEASURED_HEADROOM"
        rationale = "Oracle lift is below the minimum value delta; implementation is not justified yet."
        next_step = "Do not implement now; keep monitoring with stronger diagnostic cases or real failures."

    return FamilyDecision(
        family_id=intervention.family_id,
        display_name=intervention.display_name,
        decision=decision,
        baseline_quality_score=round(baseline_quality, 4),
        oracle_quality_score=round(oracle_quality, 4),
        quality_delta=round(delta, 4),
        affected_case_quality_delta=round(affected_case_delta, 4),
        affected_case_count=len(affected),
        affected_cases=[case.case_id for case in affected],
        residual_headroom=round(residual_headroom, 4),
        technology_examples=intervention.technology_examples,
        matching_candidates=matching_candidates,
        rationale=rationale,
        next_step=next_step,
    )


def score_case(scores: dict[str, float]) -> float:
    return sum(scores[metric] * weight for metric, weight in QUALITY_WEIGHTS.items())


def _average_case_quality(cases: list[DiagnosticCase]) -> float:
    if not cases:
        return 0.0
    return sum(score_case(case.baseline_scores) for case in cases) / len(cases)


def _affected_case_delta(cases: list[DiagnosticCase], intervention: OracleIntervention) -> float:
    if not cases:
        return 0.0
    baseline = sum(score_case(case.baseline_scores) for case in cases) / len(cases)
    oracle = sum(score_case(_apply_oracle(case.baseline_scores, intervention)) for case in cases) / len(cases)
    return oracle - baseline


def _apply_oracle(scores: dict[str, float], intervention: OracleIntervention | None) -> dict[str, float]:
    if intervention is None:
        return scores
    improved = dict(scores)
    for metric, lift in intervention.target_metrics.items():
        current = improved[metric]
        improved[metric] = min(1.0, current + (1.0 - current) * lift)
    return improved


def _load_ranked_candidates(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    return [item for item in items if isinstance(item, dict)]


def _matching_candidates(intervention: OracleIntervention, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms = [intervention.family_id.replace("_", " "), intervention.display_name.lower()]
    terms.extend(example.lower() for example in intervention.technology_examples)
    matches: list[dict[str, Any]] = []
    for candidate in candidates:
        haystack = (
            f"{candidate.get('name', '')} {candidate.get('category', '')} {candidate.get('ranking_rationale', '')}"
        )
        haystack_lower = haystack.lower()
        if any(term and term in haystack_lower for term in terms):
            matches.append(
                {
                    "candidate_id": candidate.get("candidate_id", ""),
                    "name": candidate.get("name", ""),
                    "category": candidate.get("category", ""),
                    "priority_score": candidate.get("priority_score", 0),
                    "executable": candidate.get("executable", False),
                }
            )
        if len(matches) >= 5:
            break
    return matches


def default_oracle_interventions() -> list[OracleIntervention]:
    return [
        OracleIntervention(
            family_id="counter_evidence_retrieval",
            display_name="Counter-evidence retrieval and contradiction checks",
            target_metrics={
                "contradiction_handling": 0.75,
                "unsupported_claim_control": 0.45,
                "uncertainty_calibration": 0.35,
                "evaluator_auditability": 0.20,
            },
            technology_examples=["counter-evidence retrieval", "skeptical RAG", "CRAG", "claim verification"],
            spike_shape="Add a disposable retrieval pass that searches for negative or conflicting evidence.",
        ),
        OracleIntervention(
            family_id="graphrag_evidence_graph",
            display_name="GraphRAG / evidence graph expansion",
            target_metrics={
                "lineage_traceability": 0.70,
                "evidence_sufficiency": 0.40,
                "alternatives_lost_rationale": 0.45,
                "evaluator_auditability": 0.55,
            },
            technology_examples=["GraphRAG", "knowledge graph", "evidence graph", "multi-hop graph"],
            spike_shape=(
                "Build an offline graph over startup evidence, gaps, NVIDIA technologies, and source provenance."
            ),
        ),
        OracleIntervention(
            family_id="source_trust_freshness_ranking",
            display_name="Source trust and freshness ranking",
            target_metrics={
                "source_trust_freshness": 0.70,
                "evidence_sufficiency": 0.25,
                "uncertainty_calibration": 0.25,
                "evaluator_auditability": 0.25,
            },
            technology_examples=["source-trust-aware reranking", "freshness-aware reranking", "provenance scoring"],
            spike_shape="Reorder evidence by source class, lifecycle metadata, freshness, and provenance completeness.",
        ),
        OracleIntervention(
            family_id="query_rewriting_multiquery",
            display_name="Query rewriting and multi-query expansion",
            target_metrics={
                "evidence_sufficiency": 0.55,
                "recommendation_specificity": 0.20,
                "next_action_quality": 0.15,
                "robustness_to_query_variance": 0.70,
            },
            technology_examples=["query rewriting", "query expansion", "multi-query retrieval", "HyDE"],
            spike_shape="Generate deterministic query variants from gap type, NVIDIA product, and startup vocabulary.",
        ),
        OracleIntervention(
            family_id="evidence_sufficiency_abstention",
            display_name="Evidence sufficiency and abstention gate",
            target_metrics={
                "unsupported_claim_control": 0.65,
                "uncertainty_calibration": 0.55,
                "evidence_sufficiency": 0.20,
                "evaluator_auditability": 0.25,
            },
            technology_examples=["answerability", "abstention", "uncertainty gating", "evidence verification"],
            spike_shape="Block or downgrade recommendations when required evidence coverage is missing.",
        ),
        OracleIntervention(
            family_id="recommendation_specificity_next_action",
            display_name="Recommendation specificity and next-best-action enrichment",
            target_metrics={
                "recommendation_specificity": 0.60,
                "next_action_quality": 0.65,
                "alternatives_lost_rationale": 0.25,
                "evaluator_auditability": 0.20,
            },
            technology_examples=["value-of-information", "recommendation ranking", "technical experiment templates"],
            spike_shape=(
                "Add a deterministic next-action planner that binds each recommendation to an evidence-backed "
                "experiment."
            ),
        ),
        OracleIntervention(
            family_id="cost_latency_reliability_controls",
            display_name="Cost, latency, and reliability controls",
            target_metrics={
                "operational_efficiency": 0.75,
                "robustness_to_query_variance": 0.20,
                "evaluator_auditability": 0.15,
            },
            technology_examples=["token budgeter", "context packer", "caching", "observability"],
            spike_shape=(
                "Measure whether tighter context budgets, caching, or reliability checks preserve quality with lower "
                "runtime cost."
            ),
        ),
    ]


def default_diagnostic_cases() -> list[DiagnosticCase]:
    return [
        DiagnosticCase(
            case_id="query_vocab_gap",
            name="Different vocabulary hides the right NVIDIA evidence",
            description=(
                "The startup describes model-serving needs using business terms while the corpus uses GPU inference "
                "and deployment vocabulary."
            ),
            improvement_opportunity="Improve retrieval robustness when the same need is phrased differently.",
            baseline_scores=_scores(
                evidence_sufficiency=0.48,
                recommendation_specificity=0.58,
                next_action_quality=0.62,
                lineage_traceability=0.64,
                robustness_to_query_variance=0.22,
            ),
            target_families=["query_rewriting_multiquery"],
            expected_user_value="More specific recommendations when evidence is present but phrased differently.",
        ),
        DiagnosticCase(
            case_id="multi_hop_gap_to_product",
            name="Multi-hop gap-to-product reasoning is underspecified",
            description=(
                "The output finds a technical gap and a NVIDIA product separately, but does not connect source, gap, "
                "capability, and rejected alternatives."
            ),
            improvement_opportunity="Improve explainability of why one NVIDIA path wins over adjacent options.",
            baseline_scores=_scores(
                evidence_sufficiency=0.56,
                lineage_traceability=0.30,
                alternatives_lost_rationale=0.26,
                recommendation_specificity=0.54,
                evaluator_auditability=0.34,
            ),
            target_families=["graphrag_evidence_graph"],
            expected_user_value="Clearer why this NVIDIA path wins over adjacent options.",
        ),
        DiagnosticCase(
            case_id="negative_signal_conflict",
            name="Negative signals should change confidence",
            description=(
                "The startup has positive AI claims, but evidence also indicates immature infra, stale hiring, or "
                "conflicting customer-scale claims."
            ),
            improvement_opportunity="Improve confidence calibration and evaluator trust when evidence conflicts.",
            baseline_scores=_scores(
                unsupported_claim_control=0.46,
                contradiction_handling=0.18,
                uncertainty_calibration=0.42,
                evidence_sufficiency=0.58,
                evaluator_auditability=0.44,
            ),
            target_families=["counter_evidence_retrieval", "evidence_sufficiency_abstention"],
            expected_user_value="Lower false confidence and fewer unsupported recommendations.",
        ),
        DiagnosticCase(
            case_id="stale_low_trust_sources",
            name="Stale or weak sources compete with stronger evidence",
            description=(
                "The output includes older blog/social evidence when official or fresher technical sources should "
                "dominate the support set."
            ),
            improvement_opportunity=(
                "Improve trust by preferring stronger and fresher evidence without changing the claim."
            ),
            baseline_scores=_scores(
                source_trust_freshness=0.25,
                evidence_sufficiency=0.60,
                uncertainty_calibration=0.50,
                lineage_traceability=0.58,
                evaluator_auditability=0.50,
            ),
            target_families=["source_trust_freshness_ranking"],
            expected_user_value="Higher trust in claims and recommendations because stronger sources are favored.",
        ),
        DiagnosticCase(
            case_id="insufficient_evidence_recommendation",
            name="Recommendation should abstain when support is thin",
            description=(
                "A recommendation is technically plausible, but persisted evidence and RAG support are not enough to "
                "present it as proven."
            ),
            improvement_opportunity="Improve trust by separating hypothesis from supported recommendation.",
            baseline_scores=_scores(
                evidence_sufficiency=0.34,
                unsupported_claim_control=0.38,
                uncertainty_calibration=0.36,
                recommendation_specificity=0.50,
                evaluator_auditability=0.46,
            ),
            target_families=["evidence_sufficiency_abstention"],
            expected_user_value="Avoids overclaiming and gives evaluators a trustworthy missing-evidence list.",
        ),
        DiagnosticCase(
            case_id="generic_next_action",
            name="Next action is too generic to execute",
            description=(
                "The recommendation points to a NVIDIA capability, but the next step does not specify a measurable "
                "technical experiment or success criterion."
            ),
            improvement_opportunity="Improve actionability and evaluator confidence in the proposed next step.",
            baseline_scores=_scores(
                recommendation_specificity=0.42,
                next_action_quality=0.28,
                alternatives_lost_rationale=0.40,
                evidence_sufficiency=0.66,
                evaluator_auditability=0.52,
            ),
            target_families=["recommendation_specificity_next_action"],
            expected_user_value="Turns a recommendation into an executable technical experiment.",
        ),
        DiagnosticCase(
            case_id="same_quality_lower_cost",
            name="Same quality should become cheaper and more reliable",
            description=(
                "The visible output can already be strong, but the system still benefits if context packing, budget "
                "controls, caching, or observability preserve quality with lower cost and fewer runtime surprises."
            ),
            improvement_opportunity="Improve the product as a whole even when answer quality is already acceptable.",
            baseline_scores=_scores(
                evidence_sufficiency=0.82,
                unsupported_claim_control=0.84,
                recommendation_specificity=0.80,
                next_action_quality=0.78,
                operational_efficiency=0.32,
                robustness_to_query_variance=0.58,
                evaluator_auditability=0.62,
            ),
            target_families=["cost_latency_reliability_controls"],
            expected_user_value="Keeps the answer useful while reducing cost, latency, and operational risk.",
        ),
    ]


def _scores(**overrides: float) -> dict[str, float]:
    scores = {
        "evidence_sufficiency": 0.70,
        "unsupported_claim_control": 0.72,
        "source_trust_freshness": 0.68,
        "contradiction_handling": 0.64,
        "recommendation_specificity": 0.70,
        "next_action_quality": 0.68,
        "uncertainty_calibration": 0.66,
        "lineage_traceability": 0.65,
        "alternatives_lost_rationale": 0.58,
        "robustness_to_query_variance": 0.62,
        "evaluator_auditability": 0.60,
        "operational_efficiency": 0.64,
    }
    scores.update(overrides)
    return scores


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Diagnostic Value Triage Report",
        "",
        f"Generated at: `{report['generated_at']}`",
        f"Baseline quality score: `{report['baseline_quality_score']}`",
        f"Spike candidates: `{report['spike_candidate_count']}`",
        "",
        "This report finds marginal system-value before implementing technologies. "
        "A `SPIKE_CANDIDATE` is not product adoption; it is permission to run the smallest real spike.",
        "",
        "## Recommended Spikes",
        "",
        "| Family | Affected-case delta | Global delta | Affected cases | Next step |",
        "|---|---:|---:|---:|---|",
    ]
    for decision in report["recommended_spikes"]:
        lines.append(
            f"| {_md_cell(decision['display_name'])} | {decision['affected_case_quality_delta']} | "
            f"{decision['quality_delta']} | {decision['affected_case_count']} | {_md_cell(decision['next_step'])} |"
        )
    if not report["recommended_spikes"]:
        lines.append("| None | 0 | 0 | 0 | No implementation spike is justified yet. |")
    lines.extend(
        [
            "",
            "## Family Decisions",
            "",
            "| Family | Decision | Baseline | Oracle | Affected-case delta | Global delta | Rationale |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for decision in report["family_decisions"]:
        lines.append(
            f"| {_md_cell(decision['display_name'])} | {decision['decision']} | "
            f"{decision['baseline_quality_score']} | {decision['oracle_quality_score']} | "
            f"{decision['affected_case_quality_delta']} | {decision['quality_delta']} | "
            f"{_md_cell(decision['rationale'])} |"
        )
    lines.extend(
        [
            "",
            "## Diagnostic Cases",
            "",
            "| Case | Baseline | Improvement opportunity | Target families |",
            "|---|---:|---|---|",
        ]
    )
    for case in report["case_scores"]:
        lines.append(
            f"| {_md_cell(case['name'])} | {case['baseline_quality_score']} | "
            f"{_md_cell(case['improvement_opportunity'])} | {_md_cell(', '.join(case['target_families']))} |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
