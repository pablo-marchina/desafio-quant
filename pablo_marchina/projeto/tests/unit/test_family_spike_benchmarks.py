from __future__ import annotations

import json
from pathlib import Path

from scripts import run_family_spike_benchmarks


def test_family_spike_benchmarks_test_all_promising_families() -> None:
    cases = run_family_spike_benchmarks.default_spike_cases()

    report = run_family_spike_benchmarks.build_spike_report(cases, min_real_delta=0.03)
    decisions = {decision["family_id"]: decision for decision in report["decisions"]}

    assert set(decisions) == set(run_family_spike_benchmarks.PROMISING_FAMILY_ORDER)
    assert report["tested_family_count"] == 6
    assert report["product_spike_candidate_count"] == 6
    assert all(decision["decision"] == "PROMISING_NEEDS_PRODUCT_SPIKE" for decision in decisions.values())
    assert all(decision["quality_delta"] > 0 for decision in decisions.values())


def test_query_rewriting_spike_recovers_required_evidence() -> None:
    case = next(
        item
        for item in run_family_spike_benchmarks.default_spike_cases()
        if item.family_id == "query_rewriting_multiquery"
    )

    baseline_score = run_family_spike_benchmarks.weighted_score(
        run_family_spike_benchmarks.score_output(case, case.baseline_output)
    )
    spike_output = run_family_spike_benchmarks.apply_family_spike("query_rewriting_multiquery", case)
    spike_score = run_family_spike_benchmarks.weighted_score(
        run_family_spike_benchmarks.score_output(case, spike_output)
    )

    assert "nvidia_triton_doc" in spike_output.retrieved_evidence_ids
    assert len(spike_output.query_variants) >= 3
    assert spike_score > baseline_score


def test_counter_evidence_spike_surfaces_conflict_and_recalibrates_confidence() -> None:
    case = next(
        item
        for item in run_family_spike_benchmarks.default_spike_cases()
        if item.family_id == "counter_evidence_retrieval"
    )

    spike_output = run_family_spike_benchmarks.apply_family_spike("counter_evidence_retrieval", case)
    scores = run_family_spike_benchmarks.score_output(case, spike_output)

    assert "stale_hiring_signal" in spike_output.detected_contradiction_ids
    assert spike_output.confidence < case.baseline_output.confidence
    assert scores["contradiction_handling"] == 1.0


def test_family_spike_cases_replace_empty_evidence_pack_placeholder(tmp_path: Path) -> None:
    cases_path = tmp_path / "family_spike_cases.json"
    cases_path.write_text(
        json.dumps(
            {
                "report_id": "family_spike_cases",
                "status": "PENDING_FAMILY_SPIKE_BENCHMARK_RUN",
                "cases": [],
            }
        ),
        encoding="utf-8",
    )

    cases = run_family_spike_benchmarks.load_or_write_cases(cases_path)

    assert len(cases) == len(run_family_spike_benchmarks.PROMISING_FAMILY_ORDER)
    assert cases[0].baseline_output.retrieved_evidence_ids
