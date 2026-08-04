"""Offline deterministic evaluation for final RAG/Action Brief answer quality."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from src.briefing.schemas import StartupActionBrief
from src.evaluation.answer_quality_schemas import (
    AnswerQualityEvalCase,
    AnswerQualityEvalResult,
    AnswerQualityGateResult,
    AnswerQualityMetrics,
    AnswerQualityStatus,
    EvidenceCoverageCheck,
    RequiredSectionCheck,
    UnsupportedClaim,
)

_GOLDEN_CASES_PATH = Path("examples/answer_quality/golden_answer_quality_cases.json")


def load_answer_quality_cases(path: Path = _GOLDEN_CASES_PATH) -> list[AnswerQualityEvalCase]:
    """Load versioned answer quality golden cases."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [AnswerQualityEvalCase(**item) for item in raw.get("cases", [])]


def evaluate_answer_quality(
    brief: StartupActionBrief,
    case: AnswerQualityEvalCase,
) -> AnswerQualityEvalResult:
    """Evaluate one Action Brief against one deterministic golden case."""
    section_checks = _check_required_sections(brief, case)
    answer_text = _answer_text(brief)
    unsupported_claims = _find_unsupported_claims(answer_text, case)
    forbidden_count = _count_forbidden_language(answer_text, case.forbidden_absolute_language)

    evidence_check = _coverage_check(
        "startup_evidence",
        case.required_evidence_ids,
        _startup_evidence_identifiers(brief),
    )
    gap_check = _coverage_check("gap", case.required_gap_ids, _gap_identifiers(brief))
    technology_check = _coverage_check(
        "technology",
        case.required_technology_ids,
        _technology_identifiers(brief),
    )
    rag_source_check = _coverage_check(
        "rag_source",
        case.required_rag_source_ids,
        _rag_source_identifiers(brief),
    )
    coverage_checks = [evidence_check, gap_check, technology_check, rag_source_check]

    missing_evidence_preserved = _missing_evidence_preserved(brief, case)
    uncertainty_preserved = _uncertainty_preserved(brief, case)
    motion_consistent = _recommended_motion_consistent(brief, case)
    technology_gap_consistent = _technology_gap_consistent(brief)
    rag_citation_coverage = _rag_context_citation_coverage(brief)
    startup_citation_coverage = _startup_evidence_citation_coverage(brief)

    total_claims = max(_total_claim_count(brief), 1)
    unsupported_claim_rate = round(len(unsupported_claims) / total_claims, 4)
    citation_precision = _compute_citation_precision(brief)

    metrics = AnswerQualityMetrics(
        required_sections_present=all(check.present for check in section_checks),
        missing_evidence_preserved=missing_evidence_preserved,
        uncertainty_preserved=uncertainty_preserved,
        recommended_motion_consistent=motion_consistent,
        required_evidence_ids_present=not evidence_check.missing_ids,
        required_gap_ids_present=not gap_check.missing_ids,
        required_technology_ids_present=not technology_check.missing_ids,
        unsupported_claim_count=len(unsupported_claims),
        unsupported_claim_rate=unsupported_claim_rate,
        rag_context_citation_coverage=rag_citation_coverage,
        startup_evidence_citation_coverage=startup_citation_coverage,
        citation_precision=citation_precision,
        forbidden_absolute_language_count=forbidden_count,
        answer_quality_status=AnswerQualityStatus.PASS,
        nvidia_technology_gap_consistent=technology_gap_consistent,
    )
    gates = run_answer_quality_gates(metrics, case)
    status = _aggregate_status(gates)
    metrics.answer_quality_status = status

    failures = [gate.details for gate in gates if gate.status == AnswerQualityStatus.FAIL]
    warnings = [gate.details for gate in gates if gate.status == AnswerQualityStatus.WARN]

    return AnswerQualityEvalResult(
        case_id=case.case_id,
        case_description=case.description,
        passed=status != AnswerQualityStatus.FAIL,
        metrics=metrics,
        gates=gates,
        required_section_checks=section_checks,
        evidence_coverage_checks=coverage_checks,
        unsupported_claims=unsupported_claims,
        failure_reasons=failures,
        warnings=warnings,
    )


def run_answer_quality_eval(
    briefs_by_pipeline_case_id: Mapping[str, StartupActionBrief],
    golden_path: Path = _GOLDEN_CASES_PATH,
) -> list[AnswerQualityEvalResult]:
    """Run answer quality evaluation for all golden cases with supplied briefs."""
    results: list[AnswerQualityEvalResult] = []
    for case in load_answer_quality_cases(golden_path):
        brief = briefs_by_pipeline_case_id.get(case.pipeline_case_id)
        if brief is None:
            results.append(_missing_brief_result(case))
            continue
        results.append(evaluate_answer_quality(brief, case))
    return results


def run_answer_quality_gates(
    metrics: AnswerQualityMetrics,
    case: AnswerQualityEvalCase,
) -> list[AnswerQualityGateResult]:
    """Run deterministic quality gates over computed answer quality metrics."""
    gates = [
        _gate(
            "required_sections_present",
            metrics.required_sections_present,
            "required Action Brief sections are present",
            "required Action Brief section missing",
        ),
        _gate(
            "missing_evidence_preserved",
            metrics.missing_evidence_preserved,
            "missing_evidence preserved when expected",
            "missing_evidence omitted",
        ),
        _gate(
            "uncertainty_preserved",
            metrics.uncertainty_preserved,
            "uncertainty preserved when expected",
            "uncertainty omitted for low-confidence or uncertain case",
        ),
        _gate(
            "technology_requires_gap",
            metrics.nvidia_technology_gap_consistent,
            "NVIDIA technologies map to diagnosed gaps",
            "NVIDIA technology appears without corresponding diagnosed gap",
        ),
        _gate(
            "recommended_motion_consistent",
            metrics.recommended_motion_consistent,
            "recommended_motion is consistent with expected output",
            "recommended_motion changed unexpectedly",
        ),
        _gate(
            "unsupported_claim_limit",
            metrics.unsupported_claim_count <= case.max_unsupported_claim_count,
            "unsupported claim count within limit",
            (f"unsupported_claim_count={metrics.unsupported_claim_count} exceeds {case.max_unsupported_claim_count}"),
        ),
        _gate(
            "required_evidence_ids_present",
            metrics.required_evidence_ids_present,
            "required startup evidence identifiers are present",
            "required startup evidence identifier missing",
        ),
        _gate(
            "required_gap_ids_present",
            metrics.required_gap_ids_present,
            "required gap identifiers are present",
            "required gap identifier missing",
        ),
        _gate(
            "required_technology_ids_present",
            metrics.required_technology_ids_present,
            "required NVIDIA technology identifiers are present",
            "required NVIDIA technology identifier missing",
        ),
    ]

    citation_warning = (
        metrics.rag_context_citation_coverage < case.min_rag_context_citation_coverage
        or metrics.startup_evidence_citation_coverage < case.min_startup_evidence_citation_coverage
    )
    gates.append(
        AnswerQualityGateResult(
            gate_name="citation_coverage",
            status=AnswerQualityStatus.WARN if citation_warning else AnswerQualityStatus.PASS,
            passed=not citation_warning,
            details=("citation coverage below threshold" if citation_warning else "citation coverage within threshold"),
        )
    )

    absolute_warning = metrics.forbidden_absolute_language_count > case.max_forbidden_absolute_language_count
    gates.append(
        AnswerQualityGateResult(
            gate_name="forbidden_absolute_language",
            status=AnswerQualityStatus.WARN if absolute_warning else AnswerQualityStatus.PASS,
            passed=not absolute_warning,
            details=(
                "forbidden absolute language above threshold"
                if absolute_warning
                else "forbidden absolute language within threshold"
            ),
        )
    )
    return gates


def format_answer_quality_summary(results: Sequence[AnswerQualityEvalResult]) -> str:
    """Format answer quality results for local diagnostics and JUnit failure text."""
    total = len(results)
    failed = [result for result in results if result.metrics.answer_quality_status == "FAIL"]
    warned = [result for result in results if result.metrics.answer_quality_status == "WARN"]
    lines = [
        f"Answer Quality Evaluation: {total - len(failed)}/{total} cases passed",
        (
            f"unsupported_claim_count={sum(r.metrics.unsupported_claim_count for r in results)} "
            "required_sections_missing="
            f"{sum(not r.metrics.required_sections_present for r in results)} "
            "citation_coverage="
            f"{_mean_citation_coverage(results):.4f}"
        ),
        "",
    ]
    for result in results:
        status = result.metrics.answer_quality_status.value
        lines.append(f"  [{status}] {result.case_id}: {result.case_description}")
        for reason in result.failure_reasons:
            lines.append(f"         - {reason}")
        for warning in result.warnings:
            lines.append(f"         - WARN: {warning}")
    if failed:
        lines.append(f"failed cases: {[result.case_id for result in failed]}")
    if warned:
        lines.append(f"warned cases: {[result.case_id for result in warned]}")
    return "\n".join(lines)


def _check_required_sections(
    brief: StartupActionBrief,
    case: AnswerQualityEvalCase,
) -> list[RequiredSectionCheck]:
    titles = {section.title for section in brief.sections}
    return [
        RequiredSectionCheck(section_title=section, present=section in titles) for section in case.required_sections
    ]


def _missing_evidence_preserved(
    brief: StartupActionBrief,
    case: AnswerQualityEvalCase,
) -> bool:
    if not case.expect_missing_evidence and not case.required_missing_evidence_terms:
        return True
    if not brief.missing_evidence:
        return False
    combined = " ".join(brief.missing_evidence)
    return all(_identifier_present(term, [combined]) for term in case.required_missing_evidence_terms)


def _uncertainty_preserved(
    brief: StartupActionBrief,
    case: AnswerQualityEvalCase,
) -> bool:
    requires_uncertainty = case.expect_uncertainty or (
        case.low_confidence_requires_uncertainty and str(brief.confidence.value) == "low"
    )
    if not requires_uncertainty:
        return True
    return bool(brief.uncertainties)


def _recommended_motion_consistent(
    brief: StartupActionBrief,
    case: AnswerQualityEvalCase,
) -> bool:
    if case.expected_recommended_motion:
        return brief.recommended_motion == case.expected_recommended_motion
    if case.allowed_recommended_motions:
        return brief.recommended_motion in case.allowed_recommended_motions
    return True


def _technology_gap_consistent(brief: StartupActionBrief) -> bool:
    detected_gaps = set(_gap_identifiers(brief))
    for candidate in brief.nvidia_technology_candidates:
        gap = _normalize_identifier(
            candidate.get("addresses_gap") or candidate.get("gap") or candidate.get("diagnosed_gap")
        )
        technology = _normalize_identifier(candidate.get("technology_name") or candidate.get("technology"))
        if technology and gap and gap not in detected_gaps:
            return False
    for recommendation in brief.recommendations:
        gap = _normalize_identifier(recommendation.get("diagnosed_gap") or recommendation.get("gap"))
        technologies = recommendation.get("recommended_nvidia_technologies") or []
        detected = bool(recommendation.get("detected", True))
        if technologies and (not detected or (gap and gap not in detected_gaps)):
            return False
    for supporting_context in brief.supporting_nvidia_context:
        gap = _normalize_identifier(supporting_context.gap_type)
        if gap and gap not in detected_gaps:
            return False
    return True


def _startup_evidence_citation_coverage(brief: StartupActionBrief) -> float:
    if not brief.evidence_used:
        return 1.0
    cited = sum(1 for item in brief.evidence_used if str(item.source_url or "").strip())
    return round(cited / len(brief.evidence_used), 4)


def _rag_context_citation_coverage(brief: StartupActionBrief) -> float:
    if not brief.packed_rag_contexts:
        return 1.0
    cited = sum(1 for context in brief.packed_rag_contexts if context.source_id and str(context.url or "").strip())
    return round(cited / len(brief.packed_rag_contexts), 4)


def _coverage_check(
    coverage_type: str,
    required_ids: list[str],
    present_identifiers: list[str],
) -> EvidenceCoverageCheck:
    present_required = [required for required in required_ids if _identifier_present(required, present_identifiers)]
    missing = [required for required in required_ids if required not in present_required]
    coverage = 1.0 if not required_ids else len(present_required) / len(required_ids)
    return EvidenceCoverageCheck(
        coverage_type=coverage_type,
        required_ids=required_ids,
        present_ids=present_required,
        missing_ids=missing,
        coverage=round(coverage, 4),
    )


def _startup_evidence_identifiers(brief: StartupActionBrief) -> list[str]:
    identifiers: list[str] = []
    for item in brief.evidence_used:
        identifiers.extend([item.claim, item.tag, item.source_url, item.source_type])
    for section in brief.sections:
        for item in section.items:
            identifiers.append(item.claim)
    return [_normalize_identifier(item) for item in identifiers if item]


def _gap_identifiers(brief: StartupActionBrief) -> list[str]:
    identifiers: list[str] = []
    for gap in brief.diagnosed_gaps:
        if gap.get("detected", True):
            identifiers.append(_normalize_identifier(gap.get("gap") or gap.get("diagnosed_gap")))
    for context in brief.supporting_nvidia_context:
        identifiers.append(_normalize_identifier(context.gap_type))
    return sorted({item for item in identifiers if item})


def _technology_identifiers(brief: StartupActionBrief) -> list[str]:
    identifiers: list[str] = []
    for candidate in brief.nvidia_technology_candidates:
        identifiers.append(_normalize_identifier(candidate.get("technology_name") or candidate.get("technology")))
    for recommendation in brief.recommendations:
        for technology in recommendation.get("recommended_nvidia_technologies") or []:
            identifiers.append(_normalize_identifier(technology))
    for supporting_context in brief.supporting_nvidia_context:
        identifiers.append(_normalize_identifier(supporting_context.technology))
    for packed_context in brief.packed_rag_contexts:
        identifiers.append(_normalize_identifier(packed_context.product))
        identifiers.append(_normalize_identifier(packed_context.matched_technology))
    return sorted({item for item in identifiers if item})


def _rag_source_identifiers(brief: StartupActionBrief) -> list[str]:
    identifiers = [context.source_id for context in brief.packed_rag_contexts]
    return sorted({_normalize_identifier(item) for item in identifiers if item})


def _find_unsupported_claims(
    answer_text: str,
    case: AnswerQualityEvalCase,
) -> list[UnsupportedClaim]:
    claims: list[UnsupportedClaim] = []
    for pattern in case.unsupported_claim_patterns:
        if _pattern_count(answer_text, pattern) > 0:
            claims.append(
                UnsupportedClaim(
                    claim=pattern,
                    source="answer_text",
                    reason="matched unsupported_claim_patterns in golden case",
                )
            )
    return claims


def _count_forbidden_language(answer_text: str, patterns: list[str]) -> int:
    return sum(_pattern_count(answer_text, pattern) for pattern in patterns)


def _answer_text(brief: StartupActionBrief) -> str:
    parts: list[str] = [
        brief.startup_name,
        brief.one_line_summary,
        brief.next_action_for_nvidia_team,
        brief.reasoning,
    ]
    for section in brief.sections:
        parts.extend([section.title, section.content])
        parts.extend(item.claim for item in section.items)
    return "\n".join(part for part in parts if part)


def _pattern_count(text: str, pattern: str) -> int:
    if not pattern:
        return 0
    return len(re.findall(re.escape(pattern), text, flags=re.IGNORECASE))


def _identifier_present(required: str, present_identifiers: list[str]) -> bool:
    normalized = _normalize_identifier(required)
    return any(normalized in present for present in present_identifiers)


def _normalize_identifier(value: object) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        value = value.value
    return str(value).strip().lower().replace(" ", "_")


def _total_claim_count(brief: StartupActionBrief) -> int:
    count = 0
    for section in brief.sections:
        count += len(section.items)
    return count


def _compute_citation_precision(brief: StartupActionBrief) -> float:
    packed = brief.packed_rag_contexts
    evidence = brief.evidence_used
    total_cited = len(packed) + len(evidence)
    if total_cited == 0:
        return 1.0
    rag_cited = sum(1 for c in packed if c.source_id and str(c.url or "").strip())
    ev_cited = sum(1 for e in evidence if str(e.source_url or "").strip())
    return round((rag_cited + ev_cited) / total_cited, 4)


def _gate(
    gate_name: str,
    passed: bool,
    pass_details: str,
    fail_details: str,
) -> AnswerQualityGateResult:
    return AnswerQualityGateResult(
        gate_name=gate_name,
        status=AnswerQualityStatus.PASS if passed else AnswerQualityStatus.FAIL,
        passed=passed,
        details=pass_details if passed else fail_details,
    )


def _aggregate_status(gates: list[AnswerQualityGateResult]) -> AnswerQualityStatus:
    if any(gate.status == AnswerQualityStatus.FAIL for gate in gates):
        return AnswerQualityStatus.FAIL
    if any(gate.status == AnswerQualityStatus.WARN for gate in gates):
        return AnswerQualityStatus.WARN
    return AnswerQualityStatus.PASS


def _missing_brief_result(case: AnswerQualityEvalCase) -> AnswerQualityEvalResult:
    metrics = AnswerQualityMetrics(
        required_sections_present=False,
        missing_evidence_preserved=False,
        uncertainty_preserved=False,
        recommended_motion_consistent=False,
        required_evidence_ids_present=False,
        required_gap_ids_present=False,
        required_technology_ids_present=False,
        unsupported_claim_count=0,
        unsupported_claim_rate=0.0,
        rag_context_citation_coverage=0.0,
        startup_evidence_citation_coverage=0.0,
        citation_precision=0.0,
        forbidden_absolute_language_count=0,
        answer_quality_status=AnswerQualityStatus.FAIL,
        nvidia_technology_gap_consistent=False,
    )
    return AnswerQualityEvalResult(
        case_id=case.case_id,
        case_description=case.description,
        passed=False,
        metrics=metrics,
        gates=[
            AnswerQualityGateResult(
                gate_name="brief_available",
                status=AnswerQualityStatus.FAIL,
                passed=False,
                details=f"brief not supplied for pipeline_case_id={case.pipeline_case_id}",
            )
        ],
        failure_reasons=[f"brief not supplied for pipeline_case_id={case.pipeline_case_id}"],
    )


def _mean_citation_coverage(results: Sequence[AnswerQualityEvalResult]) -> float:
    if not results:
        return 0.0
    total = sum(
        (result.metrics.rag_context_citation_coverage + result.metrics.startup_evidence_citation_coverage) / 2
        for result in results
    )
    return total / len(results)
