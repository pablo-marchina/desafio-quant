from __future__ import annotations

import json
from pathlib import Path

from scripts.build_regression_dashboard import (
    REQUIRED_MARKDOWN_SECTIONS,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARN,
    build_dashboard,
    render_markdown,
    write_dashboard,
)

REQUIRED_METRICS = [
    "documents_seen",
    "documents_valid",
    "documents_skipped",
    "chunks_created",
    "chunks_upserted",
    "sources_failed",
    "validation_errors",
    "stale_sources",
    "expired_sources",
    "deprecated_sources",
    "rag_eval_passed",
    "rag_eval_failed_cases",
    "golden_eval_passed",
    "golden_eval_failed_cases",
    "answer_quality_junit_present",
    "answer_quality_tests",
    "answer_quality_failures",
    "answer_quality_errors",
    "answer_quality_skipped",
    "answer_quality_passed",
    "answer_quality_failed_cases",
    "answer_quality_status",
    "llm_judge_report_present",
    "llm_judge_status",
    "llm_judge_provider",
    "llm_judge_total_cases",
    "llm_judge_completed_cases",
    "llm_judge_error_cases",
    "llm_judge_mean_score",
    "llm_judge_mean_faithfulness_score",
    "llm_judge_mean_answer_relevancy_score",
    "llm_judge_mean_groundedness_score",
    "llm_judge_mean_completeness_score",
    "llm_judge_mean_uncertainty_honesty_score",
    "llm_judge_mean_executive_usefulness_score",
    "action_brief_required_sections_passed",
    "missing_context_count",
    "missing_evidence_count",
]


def test_clean_reports_generate_pass(tmp_path: Path) -> None:
    _write_clean_reports(tmp_path)

    dashboard = build_dashboard(tmp_path)

    assert dashboard.status == STATUS_PASS
    assert dashboard.metrics["documents_seen"] == 10
    assert dashboard.metrics["chunks_created"] == 50
    assert dashboard.metrics["rag_eval_passed"] is True
    assert dashboard.metrics["golden_eval_passed"] is True
    assert dashboard.metrics["answer_quality_junit_present"] is True
    assert dashboard.metrics["answer_quality_status"] == STATUS_PASS
    assert dashboard.metrics["action_brief_required_sections_passed"] is True


def test_stale_sources_generate_warn(tmp_path: Path) -> None:
    _write_clean_reports(tmp_path)
    _write_json(
        tmp_path / "freshness_audit.json",
        {
            "stale_sources": 1,
            "expired_sources": 0,
            "deprecated_sources": 0,
        },
    )

    dashboard = build_dashboard(tmp_path)

    assert dashboard.status == STATUS_WARN
    assert dashboard.metrics["stale_sources"] == 1
    assert "stale_sources > 0" in dashboard.warnings


def test_validation_errors_generate_fail(tmp_path: Path) -> None:
    _write_clean_reports(tmp_path)
    _write_json(
        tmp_path / "qdrant_ingest_dry_run.json",
        {
            "documents_seen": 1,
            "documents_valid": 0,
            "documents_skipped": 1,
            "chunks_created": 0,
            "chunks_upserted": 0,
            "sources_failed": ["bad_source"],
            "validation_errors": ["missing title"],
        },
    )

    dashboard = build_dashboard(tmp_path)

    assert dashboard.status == STATUS_FAIL
    assert dashboard.metrics["validation_errors"] == 1
    assert dashboard.metrics["sources_failed"] == 1


def test_markdown_contains_required_sections(tmp_path: Path) -> None:
    _write_clean_reports(tmp_path)
    dashboard = build_dashboard(tmp_path)

    markdown = render_markdown(dashboard)

    for section in REQUIRED_MARKDOWN_SECTIONS:
        assert f"## {section}" in markdown


def test_json_contains_required_fields(tmp_path: Path) -> None:
    _write_clean_reports(tmp_path)
    dashboard = build_dashboard(tmp_path)
    _, json_path = write_dashboard(dashboard, tmp_path / "out")

    data = json.loads(json_path.read_text(encoding="utf-8"))

    assert data["status"] == STATUS_PASS
    for metric in REQUIRED_METRICS:
        assert metric in data["metrics"]
    assert isinstance(data["warnings"], list)
    assert isinstance(data["failures"], list)
    assert isinstance(data["inputs"], list)


def test_missing_reports_are_controlled_warning(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing"

    dashboard = build_dashboard(missing_dir)

    assert dashboard.status == STATUS_WARN
    assert dashboard.warnings
    for metric in REQUIRED_METRICS:
        assert metric in dashboard.metrics


def test_junit_missing_context_is_consolidated(tmp_path: Path) -> None:
    _write_clean_reports(tmp_path)
    (tmp_path / "rag_eval_junit.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="1" failures="1" errors="0" skipped="0">
  <testcase classname="tests.unit.test_rag_eval.TestRunRagEval" name="test_all_golden_queries_pass">
    <failure message="case a: missing_context_count=1&#10;case b: missing_context_count=2" />
  </testcase>
</testsuite>
""",
        encoding="utf-8",
    )

    dashboard = build_dashboard(tmp_path)

    assert dashboard.status == STATUS_FAIL
    assert dashboard.metrics["rag_eval_passed"] is False
    assert dashboard.metrics["missing_context_count"] == 3
    assert dashboard.failure_details["rag_eval"]
    assert "missing_context_count" in dashboard.failure_details["rag_eval"][0]


def test_answer_quality_junit_pass_is_consolidated(tmp_path: Path) -> None:
    _write_clean_reports(tmp_path)

    dashboard = build_dashboard(tmp_path)

    assert dashboard.status == STATUS_PASS
    assert dashboard.metrics["answer_quality_junit_present"] is True
    assert dashboard.metrics["answer_quality_tests"] == 2
    assert dashboard.metrics["answer_quality_failures"] == 0
    assert dashboard.metrics["answer_quality_errors"] == 0
    assert dashboard.metrics["answer_quality_skipped"] == 0
    assert dashboard.metrics["answer_quality_passed"] is True
    assert dashboard.metrics["answer_quality_status"] == STATUS_PASS


def test_optional_llm_judge_absent_is_info_and_non_blocking(tmp_path: Path) -> None:
    _write_clean_reports(tmp_path)

    dashboard = build_dashboard(tmp_path)

    assert dashboard.status == STATUS_PASS
    assert dashboard.metrics["llm_judge_report_present"] is False
    assert dashboard.metrics["llm_judge_status"] == "INFO"
    assert "answer_quality_llm_judge_report.json not found." not in dashboard.warnings


def test_optional_llm_judge_report_is_rendered_when_present(tmp_path: Path) -> None:
    _write_clean_reports(tmp_path)
    _write_json(
        tmp_path / "answer_quality_llm_judge_report.json",
        {
            "provider": {"provider_name": "null"},
            "total_cases": 2,
            "completed_cases": 2,
            "error_cases": 0,
            "is_ci_gate": False,
            "summary": {
                "mean_score": 0.81,
                "mean_faithfulness_score": 0.85,
                "mean_answer_relevancy_score": 0.82,
                "mean_groundedness_score": 0.84,
                "mean_completeness_score": 0.8,
                "mean_uncertainty_honesty_score": 0.88,
                "mean_executive_usefulness_score": 0.81,
            },
        },
    )

    dashboard = build_dashboard(tmp_path)
    markdown = render_markdown(dashboard)

    assert dashboard.status == STATUS_PASS
    assert dashboard.metrics["llm_judge_report_present"] is True
    assert dashboard.metrics["llm_judge_provider"] == "null"
    assert dashboard.metrics["llm_judge_total_cases"] == 2
    assert dashboard.metrics["llm_judge_mean_faithfulness_score"] == 0.85
    assert "## Optional LLM Judge" in markdown
    assert "Informational only" in markdown


def test_answer_quality_junit_failure_generates_fail(tmp_path: Path) -> None:
    _write_clean_reports(tmp_path)
    (tmp_path / "answer_quality_eval_junit.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="2" failures="1" errors="0" skipped="0">
  <testcase classname="tests.evals.test_answer_quality_golden" name="test_ok" />
  <testcase classname="tests.evals.test_answer_quality_golden" name="test_failure">
    <failure message="unsupported_claim_count=1&#10;required_sections_missing=0" />
  </testcase>
</testsuite>
""",
        encoding="utf-8",
    )

    dashboard = build_dashboard(tmp_path)

    assert dashboard.status == STATUS_FAIL
    assert dashboard.metrics["answer_quality_passed"] is False
    assert dashboard.metrics["answer_quality_failures"] == 1
    assert dashboard.metrics["answer_quality_errors"] == 0
    assert dashboard.metrics["answer_quality_failed_cases"] == 1
    assert dashboard.metrics["answer_quality_status"] == STATUS_FAIL
    assert dashboard.failed_cases["answer_quality"] == ["tests.evals.test_answer_quality_golden.test_failure"]
    assert "unsupported_claim_count=1" in dashboard.failure_details["answer_quality"][0]


def test_answer_quality_junit_error_generates_fail(tmp_path: Path) -> None:
    _write_clean_reports(tmp_path)
    (tmp_path / "answer_quality_eval_junit.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="1" failures="0" errors="1" skipped="0">
  <testcase classname="tests.evals.test_answer_quality_golden" name="test_error">
    <error message="RuntimeError: answer quality fixture failed" />
  </testcase>
</testsuite>
""",
        encoding="utf-8",
    )

    dashboard = build_dashboard(tmp_path)

    assert dashboard.status == STATUS_FAIL
    assert dashboard.metrics["answer_quality_passed"] is False
    assert dashboard.metrics["answer_quality_failures"] == 0
    assert dashboard.metrics["answer_quality_errors"] == 1
    assert dashboard.failed_cases["answer_quality"] == ["tests.evals.test_answer_quality_golden.test_error"]
    assert "RuntimeError" in dashboard.failure_details["answer_quality"][0]


def test_answer_quality_junit_skipped_does_not_fail(tmp_path: Path) -> None:
    _write_clean_reports(tmp_path)
    (tmp_path / "answer_quality_eval_junit.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="2" failures="0" errors="0" skipped="1">
  <testcase classname="tests.evals.test_answer_quality_golden" name="test_ok" />
  <testcase classname="tests.evals.test_answer_quality_golden" name="test_skipped">
    <skipped message="optional" />
  </testcase>
</testsuite>
""",
        encoding="utf-8",
    )

    dashboard = build_dashboard(tmp_path)

    assert dashboard.status == STATUS_PASS
    assert dashboard.metrics["answer_quality_tests"] == 2
    assert dashboard.metrics["answer_quality_skipped"] == 1
    assert dashboard.metrics["answer_quality_status"] == STATUS_PASS


def test_missing_answer_quality_junit_is_controlled_warning(tmp_path: Path) -> None:
    _write_clean_reports(tmp_path)
    (tmp_path / "answer_quality_eval_junit.xml").unlink()

    dashboard = build_dashboard(tmp_path)

    assert dashboard.status == STATUS_WARN
    assert dashboard.metrics["answer_quality_junit_present"] is False
    assert dashboard.metrics["answer_quality_status"] == STATUS_WARN
    assert "answer_quality_eval_junit.xml not found." in dashboard.warnings


def _write_clean_reports(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _write_json(
        path / "source_sync_dry_run.json",
        {
            "sources_seen": 10,
            "sources_failed": [],
            "validation_errors": [],
        },
    )
    _write_json(
        path / "freshness_audit.json",
        {
            "stale_sources": 0,
            "expired_sources": 0,
            "deprecated_sources": 0,
        },
    )
    _write_json(
        path / "qdrant_ingest_dry_run.json",
        {
            "documents_seen": 10,
            "documents_valid": 10,
            "documents_skipped": 0,
            "chunks_created": 50,
            "chunks_upserted": 0,
            "sources_failed": [],
            "validation_errors": [],
        },
    )
    _write_junit(path / "rag_eval_junit.xml")
    _write_junit(path / "golden_eval_junit.xml")
    _write_answer_quality_junit(path / "answer_quality_eval_junit.xml")


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_junit(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="1" failures="0" errors="0" skipped="0">
  <testcase
    classname="tests.evals.test_pipeline_golden.TestGoldenHighFit"
    name="test_action_brief_sections"
  />
</testsuite>
""",
        encoding="utf-8",
    )


def _write_answer_quality_junit(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="2" failures="0" errors="0" skipped="0">
  <testcase
    classname="tests.evals.test_answer_quality_golden"
    name="test_answer_quality_golden_cases_run_offline"
  />
  <testcase
    classname="tests.evals.test_answer_quality_golden"
    name="test_detects_unsupported_claims"
  />
</testsuite>
""",
        encoding="utf-8",
    )
