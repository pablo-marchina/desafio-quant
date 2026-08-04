"""Golden answer quality evals for Action Brief/RAG outputs."""

from __future__ import annotations

from pathlib import Path

from src.briefing.action_brief import build_action_brief
from src.briefing.schemas import BriefSection
from src.evaluation.answer_quality_eval import (
    evaluate_answer_quality,
    format_answer_quality_summary,
    load_answer_quality_cases,
    run_answer_quality_eval,
)
from src.evaluation.answer_quality_schemas import (
    AnswerQualityEvalCase,
    AnswerQualityStatus,
)
from tests.evals.helpers import load_golden_case, run_pipeline_on_case, run_pipeline_with_rag

GOLDEN_DIR = Path(__file__).resolve().parent.parent.parent / "examples" / "golden"
ANSWER_QUALITY_PATH = (
    Path(__file__).resolve().parent.parent.parent / "examples" / "answer_quality" / "golden_answer_quality_cases.json"
)


def test_answer_quality_golden_cases_run_offline() -> None:
    cases = load_answer_quality_cases(ANSWER_QUALITY_PATH)
    briefs = {_case.pipeline_case_id: _build_brief(_case) for _case in cases}

    results = run_answer_quality_eval(briefs, ANSWER_QUALITY_PATH)
    summary = format_answer_quality_summary(results)

    assert len(results) == len(cases)
    assert all(result.passed for result in results), summary
    assert all(result.metrics.answer_quality_status == AnswerQualityStatus.PASS for result in results), summary


def test_fails_when_required_section_missing() -> None:
    case = _case("high_fit_supported_answer")
    brief = _build_brief(case).model_copy(deep=True)
    brief.sections = [section for section in brief.sections if section.title != "Evidence"]

    result = evaluate_answer_quality(brief, case)

    assert result.metrics.answer_quality_status == AnswerQualityStatus.FAIL
    assert not result.metrics.required_sections_present
    assert _gate_failed(result, "required_sections_present")


def test_fails_when_missing_evidence_is_omitted() -> None:
    case = _case("weak_evidence_preserved")
    brief = _build_brief(case).model_copy(deep=True)
    brief.missing_evidence = []
    brief.sections = [section for section in brief.sections if section.title != "Missing Evidence"]

    result = evaluate_answer_quality(brief, case)

    assert result.metrics.answer_quality_status == AnswerQualityStatus.FAIL
    assert not result.metrics.missing_evidence_preserved
    assert _gate_failed(result, "missing_evidence_preserved")


def test_fails_when_uncertainty_is_omitted_for_low_confidence() -> None:
    case = _case("low_confidence_validate_manually")
    brief = _build_brief(case).model_copy(deep=True)
    brief.uncertainties = []
    brief.sections = [section for section in brief.sections if section.title != "Uncertainties / Limitations"]

    result = evaluate_answer_quality(brief, case)

    assert result.metrics.answer_quality_status == AnswerQualityStatus.FAIL
    assert not result.metrics.uncertainty_preserved
    assert _gate_failed(result, "uncertainty_preserved")


def test_fails_when_technology_appears_without_gap() -> None:
    case = _case("non_ai_no_nvidia_push")
    brief = _build_brief(case).model_copy(deep=True)
    brief.nvidia_technology_candidates = [
        {
            "technology_name": "NVIDIA NIM",
            "addresses_gap": "high_inference_cost",
            "justification": "Injected unsupported technology candidate.",
        }
    ]

    result = evaluate_answer_quality(brief, case)

    assert result.metrics.answer_quality_status == AnswerQualityStatus.FAIL
    assert not result.metrics.nvidia_technology_gap_consistent
    assert _gate_failed(result, "technology_requires_gap")


def test_fails_when_recommended_motion_changes() -> None:
    case = _case("rag_context_good_gap")
    brief = _build_brief(case).model_copy(deep=True)
    brief.recommended_motion = "immediate_outreach"

    result = evaluate_answer_quality(brief, case)

    assert result.metrics.answer_quality_status == AnswerQualityStatus.FAIL
    assert not result.metrics.recommended_motion_consistent
    assert _gate_failed(result, "recommended_motion_consistent")


def test_detects_unsupported_claims() -> None:
    case = _case("irrelevant_or_conflicting_rag_context")
    brief = _build_brief(case).model_copy(deep=True)
    brief.sections.append(
        BriefSection(
            title="Injected Unsupported Claim",
            content="unsupported guaranteed NVIDIA revenue lift",
        )
    )

    result = evaluate_answer_quality(brief, case)

    assert result.metrics.answer_quality_status == AnswerQualityStatus.FAIL
    assert result.metrics.unsupported_claim_count == 1
    assert result.unsupported_claims
    assert _gate_failed(result, "unsupported_claim_limit")


def test_warns_when_citation_coverage_is_low() -> None:
    case = _case("high_fit_supported_answer")
    brief = _build_brief(case).model_copy(deep=True)
    for context in brief.packed_rag_contexts:
        context.url = None

    result = evaluate_answer_quality(brief, case)

    assert result.metrics.answer_quality_status == AnswerQualityStatus.WARN
    assert result.metrics.rag_context_citation_coverage == 0.0
    assert _gate_warned(result, "citation_coverage")


def test_warns_when_forbidden_absolute_language_is_high() -> None:
    case = _case("high_fit_supported_answer")
    brief = _build_brief(case).model_copy(deep=True)
    brief.sections.append(
        BriefSection(
            title="Injected Absolute Language",
            content="This is guaranteed and will definitely work.",
        )
    )

    result = evaluate_answer_quality(brief, case)

    assert result.metrics.answer_quality_status == AnswerQualityStatus.WARN
    assert result.metrics.forbidden_absolute_language_count >= 2
    assert _gate_warned(result, "forbidden_absolute_language")


def _case(case_id: str) -> AnswerQualityEvalCase:
    cases = {case.case_id: case for case in load_answer_quality_cases(ANSWER_QUALITY_PATH)}
    return cases[case_id]


def _build_brief(case: AnswerQualityEvalCase):
    golden_case = load_golden_case(GOLDEN_DIR / f"{case.pipeline_case_id}.json")
    if case.use_rag:
        _, result = run_pipeline_with_rag(golden_case)
    else:
        result = run_pipeline_on_case(golden_case)
    return build_action_brief(result)


def _gate_failed(result, gate_name: str) -> bool:
    return any(gate.gate_name == gate_name and gate.status == AnswerQualityStatus.FAIL for gate in result.gates)


def _gate_warned(result, gate_name: str) -> bool:
    return any(gate.gate_name == gate_name and gate.status == AnswerQualityStatus.WARN for gate in result.gates)
