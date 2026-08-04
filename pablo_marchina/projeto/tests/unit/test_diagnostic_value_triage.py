from __future__ import annotations

import json
from pathlib import Path

from scripts import run_diagnostic_value_triage


def test_diagnostic_triage_recommends_spike_for_marginal_system_value() -> None:
    cases = run_diagnostic_value_triage.default_diagnostic_cases()

    report = run_diagnostic_value_triage.build_diagnostic_report(
        cases,
        run_diagnostic_value_triage.default_oracle_interventions(),
        min_oracle_delta=0.02,
    )

    decisions = {item["family_id"]: item for item in report["family_decisions"]}

    assert report["spike_candidate_count"] > 0
    assert decisions["graphrag_evidence_graph"]["decision"] == "SPIKE_CANDIDATE"
    assert decisions["counter_evidence_retrieval"]["decision"] == "SPIKE_CANDIDATE"
    assert report["baseline_quality_score"] < report["recommended_spikes"][0]["oracle_quality_score"]


def test_good_visible_output_can_still_have_system_value_lift() -> None:
    case = run_diagnostic_value_triage.DiagnosticCase(
        case_id="excellent_answer_expensive_runtime",
        name="Excellent answer with expensive runtime",
        description="The visible answer is strong, but the system is unnecessarily costly and fragile.",
        improvement_opportunity="Improve the product as a whole while preserving answer quality.",
        baseline_scores=run_diagnostic_value_triage._scores(
            evidence_sufficiency=0.95,
            unsupported_claim_control=0.95,
            source_trust_freshness=0.94,
            contradiction_handling=0.93,
            recommendation_specificity=0.95,
            next_action_quality=0.94,
            uncertainty_calibration=0.94,
            lineage_traceability=0.93,
            alternatives_lost_rationale=0.92,
            robustness_to_query_variance=0.72,
            evaluator_auditability=0.76,
            operational_efficiency=0.20,
        ),
        target_families=["cost_latency_reliability_controls"],
        expected_user_value="Same quality with lower cost and operational risk.",
    )
    intervention = [
        item
        for item in run_diagnostic_value_triage.default_oracle_interventions()
        if item.family_id == "cost_latency_reliability_controls"
    ]

    report = run_diagnostic_value_triage.build_diagnostic_report(
        [case],
        intervention,
        min_oracle_delta=0.02,
    )

    assert report["baseline_quality_score"] > 0.85
    assert report["recommended_spikes"][0]["family_id"] == "cost_latency_reliability_controls"
    assert report["recommended_spikes"][0]["decision"] == "SPIKE_CANDIDATE"


def test_diagnostic_triage_writes_cases_and_report(tmp_path: Path) -> None:
    cases_path = tmp_path / "diagnostic_eval_cases.json"
    report_path = tmp_path / "diagnostic_value_triage_report.json"
    markdown_path = tmp_path / "diagnostic_value_triage_report.md"

    cases = run_diagnostic_value_triage.load_or_write_cases(cases_path)
    report = run_diagnostic_value_triage.build_diagnostic_report(
        cases,
        run_diagnostic_value_triage.default_oracle_interventions(),
    )
    run_diagnostic_value_triage.write_json(report_path, report)
    run_diagnostic_value_triage.write_markdown(markdown_path, report)

    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert cases_path.is_file()
    assert markdown_path.is_file()
    assert payload["methodology"].startswith("This is a pre-implementation oracle triage")
    assert "improvement_opportunity" in payload["case_scores"][0]


def test_diagnostic_cases_replace_empty_evidence_pack_placeholder(tmp_path: Path) -> None:
    cases_path = tmp_path / "diagnostic_eval_cases.json"
    cases_path.write_text(
        json.dumps(
            {
                "report_id": "diagnostic_eval_cases",
                "status": "PENDING_DIAGNOSTIC_VALUE_TRIAGE",
                "cases": [],
            }
        ),
        encoding="utf-8",
    )

    cases = run_diagnostic_value_triage.load_or_write_cases(cases_path)

    assert len(cases) > 0
    assert cases[0].improvement_opportunity
