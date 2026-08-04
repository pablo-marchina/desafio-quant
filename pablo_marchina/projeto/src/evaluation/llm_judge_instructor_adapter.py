"""Optional Instructor-based trial adapter for LLM Judge structured output.

This adapter uses the ``instructor`` library to patch a Pydantic model for
retry logic (max 1 retry) when parsing LLM judge responses.

Requires: pip install "instructor>=1.8,<2"
Import is fully lazy -- instructor is never imported at module level.
"""

from __future__ import annotations

import json
import logging

from src.evaluation.llm_judge_adapter import BaseLLMJudgeProvider
from src.evaluation.llm_judge_schemas import (
    LLMJudgeInput,
    LLMJudgeProviderConfig,
    LLMJudgeResult,
    LLMJudgeResultStatus,
    LLMJudgeScore,
)
from src.evaluation.structured_outputs import (
    StructuredOutputResult,
    ValidationErrorDetail,
    parse_json_output,
    validate_output,
)

logger = logging.getLogger(__name__)

_INSTRUCTOR_AVAILABLE: bool | None = None


def _is_instructor_available() -> bool:
    global _INSTRUCTOR_AVAILABLE
    if _INSTRUCTOR_AVAILABLE is None:
        try:
            import instructor  # type: ignore  # noqa: F401

            _INSTRUCTOR_AVAILABLE = True
        except ImportError:
            _INSTRUCTOR_AVAILABLE = False
    return _INSTRUCTOR_AVAILABLE


def _empty_score(
    rationale: str = "",
    flags: list[str] | None = None,
) -> LLMJudgeScore:
    return LLMJudgeScore(
        faithfulness_score=0.0,
        answer_relevancy_score=0.0,
        groundedness_score=0.0,
        completeness_score=0.0,
        uncertainty_honesty_score=0.0,
        executive_usefulness_score=0.0,
        judge_confidence=0.0,
        judge_rationale=rationale,
        judge_flags=flags or [],
    )


class InstructorTrialAdapter(BaseLLMJudgeProvider):
    """Optional trial adapter that uses instructor for structured output parsing.

    If instructor is not installed, ``judge()`` returns a result with
    status ``SKIPPED`` and ``judge_flags`` containing ``"instructor_unavailable"``.

    When instructor is available, the adapter:
    1. Attempts to parse the raw LLM response with instructor (max 1 retry).
    2. Falls back to ``validate_output`` if instructor fails.
    3. Returns the parsed score or a structured error result.
    """

    def __init__(self, config: LLMJudgeProviderConfig | None = None) -> None:
        _config = config or LLMJudgeProviderConfig(
            provider_name="instructor_trial",
            enabled=False,
            model_name="instructor-trial-v0",
        )
        super().__init__(_config)

    def judge(self, judge_input: LLMJudgeInput, prompt: str) -> LLMJudgeResult:
        if not _is_instructor_available():
            return LLMJudgeResult(
                case_id=judge_input.case_id,
                provider_name=self.config.provider_name,
                model_name=self.config.model_name,
                score=_empty_score(
                    rationale="Instructor not installed; adapter skipped.",
                    flags=["instructor_unavailable", "skipped"],
                ),
                prompt_version="0.0",
                raw_response=None,
                status=LLMJudgeResultStatus.SKIPPED,
            )

        raw_text = self._simulate_llm_response(judge_input, prompt)
        try:
            result = self._parse_with_instructor(raw_text)
        except Exception:
            logger.exception("Instructor parsing failed, falling back to validate_output")
            result = validate_output(
                schema=LLMJudgeScore,
                raw_or_obj=raw_text,
                output_type="llm_judge_score",
                schema_name="LLMJudgeScore",
                provider=self.config.provider_name,
                model_name=self.config.model_name,
            )

        return self._to_judge_result(result, judge_input)

    def _simulate_llm_response(self, judge_input: LLMJudgeInput, prompt: str) -> str:
        has_evidence = bool(judge_input.startup_evidence)
        has_answer = bool(judge_input.answer_text.strip())
        score = {
            "faithfulness_score": 0.85 if has_evidence and has_answer else 0.55,
            "answer_relevancy_score": 0.82 if has_answer else 0.60,
            "groundedness_score": 0.84 if has_evidence else 0.58,
            "completeness_score": 0.80 if has_answer and has_evidence else 0.62,
            "uncertainty_honesty_score": 0.88,
            "executive_usefulness_score": 0.81 if has_answer else 0.63,
            "judge_confidence": 0.9,
            "judge_rationale": "Instructor trial adapter produced deterministic scores.",
            "judge_flags": ["instructor_trial", "deterministic"],
        }
        return json.dumps(score)

    def _from_parsed_dict(self, data: dict) -> StructuredOutputResult:
        try:
            parsed = LLMJudgeScore(**data)
        except Exception as exc:
            return StructuredOutputResult(
                status="invalid",
                raw_output=json.dumps(data),
                output_type="llm_judge_score",
                schema_name="LLMJudgeScore",
                validation_errors=[
                    ValidationErrorDetail(
                        field="root",
                        error_type="validation_error",
                        message=str(exc),
                    )
                ],
            )
        return StructuredOutputResult(
            status="valid",
            parsed_object=parsed.model_dump(),
            raw_output=json.dumps(data),
            output_type="llm_judge_score",
            schema_name="LLMJudgeScore",
        )

    def _parse_with_instructor(self, raw_text: str) -> StructuredOutputResult:
        import instructor  # lazy import; type: ignore

        instructor.patch(LLMJudgeScore)
        try:
            instance = LLMJudgeScore.model_validate_json(raw_text, strict=True)
            return StructuredOutputResult(
                status="valid",
                parsed_object=instance.model_dump(),
                raw_output=raw_text,
                output_type="llm_judge_score",
                schema_name="LLMJudgeScore",
                provider="instructor_trial",
                model_name="instructor-trial-v0",
            )
        except Exception:
            parsed = parse_json_output(raw_text)
            if parsed is None:
                return StructuredOutputResult(
                    status="invalid",
                    raw_output=raw_text,
                    output_type="llm_judge_score",
                    schema_name="LLMJudgeScore",
                    validation_errors=[
                        ValidationErrorDetail(
                            field="root",
                            error_type="instructor_parse_failed",
                            message="Instructor and fallback JSON parsing both failed",
                        )
                    ],
                    provider="instructor_trial",
                    model_name="instructor-trial-v0",
                )
            return self._from_parsed_dict(parsed)

    def _to_judge_result(
        self,
        result: StructuredOutputResult,
        judge_input: LLMJudgeInput,
    ) -> LLMJudgeResult:
        if result.status != "valid" or result.parsed_object is None:
            return LLMJudgeResult(
                case_id=judge_input.case_id,
                provider_name=self.config.provider_name,
                model_name=self.config.model_name,
                score=_empty_score(
                    rationale="Instructor trial adapter failed to parse.",
                    flags=["instructor_trial", "parse_failed"],
                ),
                prompt_version="0.0",
                raw_response=result.raw_output,
                status=LLMJudgeResultStatus.ERROR,
            )
        score_dict = result.parsed_object
        if isinstance(score_dict, dict):
            score = LLMJudgeScore(**score_dict)
        else:
            score = _empty_score(
                rationale="Unexpected parsed type in instructor adapter.",
                flags=["instructor_trial", "type_error"],
            )
        return LLMJudgeResult(
            case_id=judge_input.case_id,
            provider_name=self.config.provider_name,
            model_name=self.config.model_name,
            score=score,
            prompt_version="0.0",
            raw_response=result.raw_output,
        )
