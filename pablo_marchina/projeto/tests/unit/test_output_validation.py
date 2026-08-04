from __future__ import annotations

from copy import deepcopy

from src.validation.output_validation import (
    validate_action_brief_output,
    validate_api_response_output,
    validate_dashboard_output,
    validate_markdown_output,
)
from src.validation.output_validation_schemas import OutputValidationStatus


def _evidence_item() -> dict:
    return {
        "claim": "Startup uses computer vision models in production.",
        "tag": "fact",
        "confidence": "high",
        "source_url": "https://example.com/evidence",
        "source_type": "official_site",
    }


def _validated_evidence() -> dict:
    return {
        "claim": "Startup uses computer vision models in production.",
        "source_url": "https://example.com/evidence",
        "source_type": "official_site",
        "quote_or_evidence": "The company states it uses computer vision models in production.",
        "confidence": "high",
        "evidence_kind": "fact",
        "collected_at": "2026-06-11T00:00:00Z",
    }


def _section(title: str) -> dict:
    return {"title": title, "content": f"{title} content.", "items": []}


def _valid_brief() -> dict:
    return {
        "startup_name": "Nexus AI Labs",
        "website": "https://example.com",
        "sector": "HealthTech",
        "one_line_summary": "AI healthcare platform.",
        "verdict": "promising",
        "final_priority_score": 72.5,
        "recommended_motion": "monitor_and_nurture",
        "confidence": "high",
        "sections": [
            _section("Executive Summary"),
            _section("Why This Startup Matters"),
            _section("AI-Native Maturity"),
            _section("Scores Overview"),
            _section("Production AI Gaps"),
            _section("NVIDIA Fit"),
            _section("Recommended NVIDIA Technologies"),
            _section("Recommended Motion"),
            {"title": "Evidence", "content": "Evidence content.", "items": [_evidence_item()]},
            _section("Next Action"),
        ],
        "ai_native_classification": {"level": "ai_native", "confidence": "high"},
        "defensibility_score": {"total_score": 70.0},
        "inception_fit_score": {"total_score": 75.0},
        "production_readiness_score": {"total_score": 68.0},
        "composite_score": {"final_score": 72.5},
        "diagnosed_gaps": [
            {
                "gap": "computer_vision_need",
                "detected": True,
                "confidence": "high",
                "evidence_tag": "fact",
                "reasoning": "Computer vision workload detected.",
            }
        ],
        "nvidia_technology_candidates": [
            {
                "technology_name": "NVIDIA TensorRT",
                "addresses_gap": "computer_vision_need",
                "justification": "Optimizes vision inference.",
            }
        ],
        "recommendations": [
            {
                "diagnosed_gap": "computer_vision_need",
                "detected": True,
                "recommended_nvidia_technologies": ["NVIDIA TensorRT"],
                "technical_justification": "Vision inference optimization.",
                "business_justification": "Lower latency.",
                "priority": "high",
                "implementation_complexity": "medium",
                "suggested_experiment": None,
                "action": "approach_now",
                "next_action_for_nvidia_team": "Validate workload.",
                "evidence_used": [_validated_evidence()],
                "missing_evidence": [],
                "confidence": "high",
            }
        ],
        "evidence_used": [_evidence_item()],
        "missing_evidence": [],
        "uncertainties": [],
        "next_action_for_nvidia_team": "Validate workload.",
        "reasoning": "Evidence-backed recommendation.",
    }


def _dashboard() -> dict:
    return {
        "dashboard_version": "1.0",
        "generated_at": "2026-06-11T00:00:00Z",
        "status": "PASS",
        "metrics": {
            "documents_seen": 1,
            "documents_valid": 1,
            "validation_errors": 0,
            "rag_eval_passed": True,
            "golden_eval_passed": True,
            "answer_quality_junit_present": True,
            "answer_quality_tests": 9,
            "answer_quality_failures": 0,
            "answer_quality_errors": 0,
            "answer_quality_skipped": 0,
            "answer_quality_passed": True,
            "answer_quality_status": "PASS",
            "action_brief_required_sections_passed": True,
            "missing_evidence_count": 0,
            "unsupported_claim_count": 0,
            "required_sections_missing": 0,
            "citation_coverage": 1.0,
        },
        "warnings": [],
        "failures": [],
        "inputs": [],
    }


def test_valid_action_brief_passes() -> None:
    result = validate_action_brief_output(_valid_brief())

    assert result.status == OutputValidationStatus.PASS
    assert not result.failures


def test_action_brief_missing_section_fails() -> None:
    brief = _valid_brief()
    brief["sections"] = [section for section in brief["sections"] if section["title"] != "Evidence"]

    result = validate_action_brief_output(brief)

    assert result.status == OutputValidationStatus.FAIL
    assert any("missing required sections" in failure for failure in result.failures)


def test_action_brief_invalid_recommended_motion_fails() -> None:
    brief = _valid_brief()
    brief["recommended_motion"] = "call_immediately"

    result = validate_action_brief_output(brief)

    assert result.status == OutputValidationStatus.FAIL
    assert any("Invalid recommended_motion" in failure for failure in result.failures)


def test_action_brief_invalid_gap_id_fails() -> None:
    brief = _valid_brief()
    brief["diagnosed_gaps"][0]["gap"] = "unknown_gap"

    result = validate_action_brief_output(brief)

    assert result.status == OutputValidationStatus.FAIL
    assert any("invalid gap ids" in failure for failure in result.failures)


def test_action_brief_invalid_nvidia_technology_fails() -> None:
    brief = _valid_brief()
    brief["recommendations"][0]["recommended_nvidia_technologies"] = ["NVIDIA Clara"]

    result = validate_action_brief_output(brief)

    assert result.status == OutputValidationStatus.FAIL
    assert any("outside the mapping matrix" in failure for failure in result.failures)


def test_action_brief_missing_evidence_field_fails() -> None:
    brief = _valid_brief()
    del brief["missing_evidence"]

    result = validate_action_brief_output(brief)

    assert result.status == OutputValidationStatus.FAIL
    assert any("StartupActionBrief schema" in failure for failure in result.failures)


def test_action_brief_recommendation_without_evidence_fails() -> None:
    brief = _valid_brief()
    brief["recommendations"][0]["evidence_used"] = []

    result = validate_action_brief_output(brief)

    assert result.status == OutputValidationStatus.FAIL
    assert any("must include evidence_used" in failure for failure in result.failures)


def test_dashboard_missing_required_key_fails() -> None:
    dashboard = _dashboard()
    del dashboard["metrics"]["golden_eval_passed"]

    result = validate_dashboard_output(dashboard)

    assert result.status == OutputValidationStatus.FAIL
    assert any("missing required metrics" in failure for failure in result.failures)


def test_markdown_todo_generates_warning_not_failure() -> None:
    markdown = """
# Startup Action Brief

## Executive Summary
Ready.

## Recommended Motion
TODO: fill later.

## Evidence
Evidence is present.

## Next Action
Validate manually.
""".strip()

    result = validate_markdown_output(markdown)

    assert result.status == OutputValidationStatus.WARN
    assert any("unresolved placeholders" in warning for warning in result.warnings)


def test_markdown_empty_critical_section_fails() -> None:
    markdown = """
## Executive Summary

## Recommended Motion
Monitor.

## Evidence
Evidence is present.

## Next Action
Validate manually.
""".strip()

    result = validate_markdown_output(markdown)

    assert result.status == OutputValidationStatus.FAIL
    assert any("empty critical sections" in failure for failure in result.failures)


def test_api_brief_response_preserves_warnings() -> None:
    api_response = {
        "run_id": "run-1",
        "startup_name": "Nexus AI Labs",
        "brief_json": _valid_brief(),
        "brief_markdown": "# Brief",
        "run_report": {"status": "ok"},
        "answer_quality_eval": None,
        "warnings": ["Qdrant unavailable; used local mode."],
    }

    result = validate_api_response_output(api_response, response_type="brief")

    assert result.status == OutputValidationStatus.PASS


def test_low_confidence_brief_requires_uncertainty() -> None:
    brief = deepcopy(_valid_brief())
    brief["confidence"] = "low"

    result = validate_action_brief_output(brief)

    assert result.status == OutputValidationStatus.FAIL
    assert any("Low-confidence" in failure for failure in result.failures)
