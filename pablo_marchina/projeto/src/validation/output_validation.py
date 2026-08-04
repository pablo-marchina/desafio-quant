"""Deterministic validators for generated workspace outputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from src.api.schemas import (
    ArtifactListResponse,
    BriefResponse,
    EvaluateResponse,
    RagStatusResponse,
    VersionResponse,
)
from src.briefing.schemas import StartupActionBrief
from src.diagnosis.nvidia_mapping import map_gap_to_technologies
from src.extraction.schemas import ConfidenceLevel, TechnicalGap
from src.validation.output_validation_schemas import (
    OutputValidationResult,
    OutputValidationSeverity,
    OutputValidationStatus,
)

ALLOWED_RECOMMENDED_MOTIONS = {
    "immediate_outreach",
    "high_priority_outreach",
    "monitor_and_nurture",
    "lack_evidence_more_research",
    "not_recommended",
}

REQUIRED_BRIEF_SECTIONS = {
    "Executive Summary",
    "Why This Startup Matters",
    "AI-Native Maturity",
    "Scores Overview",
    "Production AI Gaps",
    "NVIDIA Fit",
    "Recommended NVIDIA Technologies",
    "Recommended Motion",
    "Evidence",
    "Next Action",
}

CRITICAL_MARKDOWN_SECTIONS = {
    "Executive Summary",
    "Recommended Motion",
    "Evidence",
    "Next Action",
}

REQUIRED_DASHBOARD_METRICS = {
    "documents_seen",
    "documents_valid",
    "validation_errors",
    "rag_eval_passed",
    "golden_eval_passed",
    "answer_quality_junit_present",
    "answer_quality_tests",
    "answer_quality_failures",
    "answer_quality_errors",
    "answer_quality_skipped",
    "answer_quality_passed",
    "answer_quality_status",
    "action_brief_required_sections_passed",
    "missing_evidence_count",
}

ANSWER_QUALITY_METRICS = {
    "unsupported_claim_count",
    "required_sections_missing",
    "citation_coverage",
}

JUNIT_METRICS = {
    "answer_quality_tests",
    "answer_quality_failures",
    "answer_quality_errors",
    "answer_quality_skipped",
}

API_RESPONSE_SCHEMAS = {
    "version": VersionResponse,
    "rag_status": RagStatusResponse,
    "brief": BriefResponse,
    "evaluate": EvaluateResponse,
    "artifacts": ArtifactListResponse,
}


def validate_action_brief_output(data: Mapping[str, Any]) -> OutputValidationResult:
    result = OutputValidationResult.empty("action_brief_json")
    try:
        brief = StartupActionBrief(**dict(data))
    except ValidationError as exc:
        result.add_check(
            "action_brief_schema",
            OutputValidationStatus.FAIL,
            f"Action Brief does not match StartupActionBrief schema: {exc.errors()}",
            field="root",
        )
        return result

    _check_required_brief_sections(result, brief)
    _check_recommended_motion(result, brief.recommended_motion)
    _check_score_ranges(result, brief)
    _check_gap_ids(result, brief)
    _check_nvidia_technology_ids(result, brief)
    _check_evidence_traceability(result, brief)
    _check_low_confidence_uncertainty(result, brief)
    _check_missing_evidence_preserved(result, data)
    _check_critical_sections_not_empty(result, brief)
    return result


def validate_markdown_output(
    text: str,
    *,
    required_headings: Sequence[str] | None = None,
    critical_headings: Sequence[str] | None = None,
) -> OutputValidationResult:
    result = OutputValidationResult.empty("markdown")
    required = set(required_headings or CRITICAL_MARKDOWN_SECTIONS)
    critical = set(critical_headings or required)
    headings = _extract_markdown_headings(text)

    missing = sorted(required - headings)
    if missing:
        result.add_check(
            "markdown_required_headings",
            OutputValidationStatus.FAIL,
            f"Markdown is missing required headings: {', '.join(missing)}",
        )
    else:
        result.add_check(
            "markdown_required_headings",
            OutputValidationStatus.PASS,
            "All required headings are present.",
            severity=OutputValidationSeverity.INFO,
        )

    placeholders = ["TODO", "TBD", "{", "}"]
    unresolved = [item for item in placeholders if item in text]
    if unresolved:
        result.add_check(
            "markdown_unresolved_placeholders",
            OutputValidationStatus.WARN,
            f"Markdown contains possible unresolved placeholders: {', '.join(unresolved)}",
            severity=OutputValidationSeverity.WARN,
        )

    empty_sections = sorted(heading for heading in critical if _section_is_empty(text, heading))
    if empty_sections:
        result.add_check(
            "markdown_empty_critical_sections",
            OutputValidationStatus.FAIL,
            f"Markdown has empty critical sections: {', '.join(empty_sections)}",
        )

    return result


def validate_dashboard_output(data: Mapping[str, Any]) -> OutputValidationResult:
    result = OutputValidationResult.empty("regression_dashboard_json")
    status = data.get("status")
    if status not in {"PASS", "WARN", "FAIL"}:
        result.add_check(
            "dashboard_status",
            OutputValidationStatus.FAIL,
            "Dashboard status must be one of PASS, WARN, FAIL.",
            field="status",
        )

    metrics = data.get("metrics")
    if not isinstance(metrics, Mapping):
        result.add_check(
            "dashboard_metrics",
            OutputValidationStatus.FAIL,
            "Dashboard metrics must be an object.",
            field="metrics",
        )
        return result

    missing_metrics = sorted(REQUIRED_DASHBOARD_METRICS - set(metrics))
    if missing_metrics:
        result.add_check(
            "dashboard_required_metrics",
            OutputValidationStatus.FAIL,
            f"Dashboard is missing required metrics: {', '.join(missing_metrics)}",
            field="metrics",
        )
    else:
        result.add_check(
            "dashboard_required_metrics",
            OutputValidationStatus.PASS,
            "Dashboard required metrics are present.",
            severity=OutputValidationSeverity.INFO,
        )

    if metrics.get("answer_quality_junit_present") is True:
        missing_junit = sorted(JUNIT_METRICS - set(metrics))
        if missing_junit:
            result.add_check(
                "dashboard_junit_metrics",
                OutputValidationStatus.FAIL,
                f"Dashboard is missing JUnit metrics: {', '.join(missing_junit)}",
                field="metrics",
            )

    answer_quality_status = metrics.get("answer_quality_status")
    if answer_quality_status not in {"PASS", "WARN", "FAIL", "not run"}:
        result.add_check(
            "dashboard_answer_quality_status",
            OutputValidationStatus.FAIL,
            "answer_quality_status must be PASS, WARN, FAIL, or not run.",
            field="metrics.answer_quality_status",
        )

    missing_answer_metrics = sorted(ANSWER_QUALITY_METRICS - set(metrics))
    if missing_answer_metrics:
        result.add_check(
            "dashboard_answer_quality_metrics",
            OutputValidationStatus.WARN,
            ("Dashboard does not expose all answer quality detail metrics: " + ", ".join(missing_answer_metrics)),
            severity=OutputValidationSeverity.WARN,
            field="metrics",
        )
    return result


def validate_api_response_output(
    data: Mapping[str, Any],
    *,
    response_type: str,
) -> OutputValidationResult:
    result = OutputValidationResult.empty("api_response_json")
    schema = API_RESPONSE_SCHEMAS.get(response_type)
    if schema is None:
        result.add_check(
            "api_response_schema",
            OutputValidationStatus.WARN,
            f"No API response schema registered for response_type={response_type}.",
            severity=OutputValidationSeverity.WARN,
        )
        return result

    try:
        response = schema(**dict(data))
    except ValidationError as exc:
        result.add_check(
            "api_response_schema",
            OutputValidationStatus.FAIL,
            f"API response does not match {schema.__name__}: {exc.errors()}",
            field="root",
        )
        return result

    if hasattr(response, "warnings") and not isinstance(response.warnings, list):
        result.add_check(
            "api_response_warnings",
            OutputValidationStatus.FAIL,
            "API response warnings must be preserved as a list.",
            field="warnings",
        )

    if isinstance(response, RagStatusResponse) and not response.qdrant_available:
        if not response.error:
            result.add_check(
                "api_rag_status_warning",
                OutputValidationStatus.WARN,
                "Qdrant offline status should expose a controlled error or warning.",
                severity=OutputValidationSeverity.WARN,
                field="error",
            )

    return result


def _check_required_brief_sections(
    result: OutputValidationResult,
    brief: StartupActionBrief,
) -> None:
    section_titles = {section.title for section in brief.sections}
    missing = sorted(REQUIRED_BRIEF_SECTIONS - section_titles)
    if missing:
        result.add_check(
            "brief_required_sections",
            OutputValidationStatus.FAIL,
            f"Action Brief is missing required sections: {', '.join(missing)}",
            field="sections",
        )
    else:
        result.add_check(
            "brief_required_sections",
            OutputValidationStatus.PASS,
            "Action Brief required sections are present.",
            severity=OutputValidationSeverity.INFO,
        )


def _check_recommended_motion(
    result: OutputValidationResult,
    recommended_motion: str,
) -> None:
    if recommended_motion not in ALLOWED_RECOMMENDED_MOTIONS:
        result.add_check(
            "brief_recommended_motion",
            OutputValidationStatus.FAIL,
            f"Invalid recommended_motion: {recommended_motion}.",
            field="recommended_motion",
        )


def _check_score_ranges(
    result: OutputValidationResult,
    brief: StartupActionBrief,
) -> None:
    if not 0 <= brief.final_priority_score <= 100:
        result.add_check(
            "brief_final_priority_score",
            OutputValidationStatus.FAIL,
            "final_priority_score must be between 0 and 100.",
            field="final_priority_score",
        )
    score_fields = {
        "defensibility_score": brief.defensibility_score,
        "inception_fit_score": brief.inception_fit_score,
        "production_readiness_score": brief.production_readiness_score,
        "composite_score": brief.composite_score,
    }
    for field_name, payload in score_fields.items():
        for key, value in payload.items():
            if key.endswith("score") and isinstance(value, int | float) and not 0 <= value <= 100:
                result.add_check(
                    "brief_nested_score_range",
                    OutputValidationStatus.FAIL,
                    f"{field_name}.{key} must be between 0 and 100.",
                    field=f"{field_name}.{key}",
                )


def _check_gap_ids(result: OutputValidationResult, brief: StartupActionBrief) -> None:
    valid_gaps = {gap.value for gap in TechnicalGap}
    invalid: list[str] = []
    for gap in brief.diagnosed_gaps:
        gap_id = str(gap.get("gap", ""))
        if gap_id not in valid_gaps:
            invalid.append(gap_id)
    for recommendation in brief.recommendations:
        gap_id = str(recommendation.get("diagnosed_gap", ""))
        if gap_id and gap_id not in valid_gaps:
            invalid.append(gap_id)
    if invalid:
        result.add_check(
            "brief_valid_gap_ids",
            OutputValidationStatus.FAIL,
            f"Action Brief has invalid gap ids: {', '.join(sorted(set(invalid)))}",
            field="diagnosed_gaps",
        )


def _check_nvidia_technology_ids(
    result: OutputValidationResult,
    brief: StartupActionBrief,
) -> None:
    invalid: list[str] = []
    for recommendation in brief.recommendations:
        gap_id = recommendation.get("diagnosed_gap")
        if gap_id not in {gap.value for gap in TechnicalGap}:
            continue
        allowed = {candidate.technology_name for candidate in map_gap_to_technologies(TechnicalGap(str(gap_id)))}
        for technology in recommendation.get("recommended_nvidia_technologies") or []:
            if technology not in allowed:
                invalid.append(f"{technology} for {gap_id}")
    for candidate in brief.nvidia_technology_candidates:
        gap_id = candidate.get("addresses_gap")
        technology = candidate.get("technology_name")
        if gap_id not in {gap.value for gap in TechnicalGap}:
            continue
        allowed = {mapped.technology_name for mapped in map_gap_to_technologies(TechnicalGap(str(gap_id)))}
        if technology not in allowed:
            invalid.append(f"{technology} for {gap_id}")
    if invalid:
        result.add_check(
            "brief_valid_nvidia_technologies",
            OutputValidationStatus.FAIL,
            "Action Brief has NVIDIA technologies outside the mapping matrix: " + ", ".join(sorted(set(invalid))),
            field="recommendations",
        )


def _check_evidence_traceability(
    result: OutputValidationResult,
    brief: StartupActionBrief,
) -> None:
    if not brief.evidence_used:
        result.add_check(
            "brief_evidence_used",
            OutputValidationStatus.FAIL,
            "Action Brief must preserve evidence_used.",
            field="evidence_used",
        )
    for index, recommendation in enumerate(brief.recommendations):
        technologies = recommendation.get("recommended_nvidia_technologies") or []
        evidence = recommendation.get("evidence_used") or []
        if technologies and not evidence:
            result.add_check(
                "brief_recommendation_evidence",
                OutputValidationStatus.FAIL,
                "Recommendation with NVIDIA technology must include evidence_used.",
                field=f"recommendations.{index}.evidence_used",
            )


def _check_low_confidence_uncertainty(
    result: OutputValidationResult,
    brief: StartupActionBrief,
) -> None:
    if brief.confidence == ConfidenceLevel.LOW and not brief.uncertainties:
        result.add_check(
            "brief_low_confidence_uncertainty",
            OutputValidationStatus.FAIL,
            "Low-confidence Action Brief must include uncertainties.",
            field="uncertainties",
        )


def _check_missing_evidence_preserved(
    result: OutputValidationResult,
    data: Mapping[str, Any],
) -> None:
    if "missing_evidence" not in data:
        result.add_check(
            "brief_missing_evidence",
            OutputValidationStatus.FAIL,
            "Action Brief must include missing_evidence, even when empty.",
            field="missing_evidence",
        )


def _check_critical_sections_not_empty(
    result: OutputValidationResult,
    brief: StartupActionBrief,
) -> None:
    empty = sorted(
        section.title
        for section in brief.sections
        if section.title in CRITICAL_MARKDOWN_SECTIONS and not section.content.strip()
    )
    if empty:
        result.add_check(
            "brief_empty_critical_sections",
            OutputValidationStatus.FAIL,
            f"Action Brief has empty critical sections: {', '.join(empty)}",
            field="sections",
        )


def _extract_markdown_headings(text: str) -> set[str]:
    headings: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            headings.add(stripped.lstrip("#").strip())
    return headings


def _section_is_empty(text: str, heading: str) -> bool:
    lines = text.splitlines()
    in_section = False
    content: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            current = stripped.lstrip("#").strip()
            if in_section:
                break
            if current == heading:
                in_section = True
            continue
        if in_section:
            content.append(stripped)
    return in_section and not any(item for item in content)
