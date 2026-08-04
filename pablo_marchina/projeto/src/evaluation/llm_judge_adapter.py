"""Optional LLM judge adapter for answer quality review."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import UTC, datetime

from src.evaluation.llm_judge_prompts import PROMPT_VERSION, build_llm_judge_prompt
from src.evaluation.llm_judge_schemas import (
    LLMJudgeInput,
    LLMJudgeProviderConfig,
    LLMJudgeResult,
    LLMJudgeRunReport,
    LLMJudgeScore,
)


class BaseLLMJudgeProvider(ABC):
    """Base class for optional judge providers."""

    def __init__(self, config: LLMJudgeProviderConfig | None = None) -> None:
        self.config = config or LLMJudgeProviderConfig()

    @abstractmethod
    def judge(self, judge_input: LLMJudgeInput, prompt: str) -> LLMJudgeResult:
        """Judge one answer quality case."""


class NullLLMJudgeProvider(BaseLLMJudgeProvider):
    """Deterministic offline provider used for tests and local plumbing checks."""

    def __init__(self, config: LLMJudgeProviderConfig | None = None) -> None:
        null_config = config or LLMJudgeProviderConfig(
            provider_name="null",
            enabled=False,
            model_name="null-offline-deterministic",
        )
        super().__init__(null_config)

    def judge(self, judge_input: LLMJudgeInput, prompt: str) -> LLMJudgeResult:
        """Return predictable scores without reading network, API keys, or models."""
        has_evidence = bool(judge_input.startup_evidence)
        has_gap = bool(judge_input.diagnosed_gaps)
        has_uncertainty = bool(judge_input.uncertainties or judge_input.missing_evidence)
        has_rag = bool(judge_input.rag_contexts)
        has_recommendation = bool(judge_input.recommendations)
        has_answer = bool(judge_input.answer_text.strip())

        score = LLMJudgeScore(
            faithfulness_score=0.85 if has_evidence and has_answer else 0.55,
            answer_relevancy_score=0.82 if has_answer and (has_gap or has_recommendation) else 0.60,
            groundedness_score=0.84 if has_evidence and (has_rag or has_gap) else 0.58,
            completeness_score=0.80 if has_answer and has_evidence and has_recommendation else 0.62,
            uncertainty_honesty_score=0.88 if has_uncertainty else 0.70,
            executive_usefulness_score=0.81 if has_answer and has_recommendation else 0.63,
            judge_confidence=1.0,
            judge_rationale=(
                "NullLLMJudgeProvider produced deterministic offline scores for plumbing "
                "and report validation only; no semantic model was called."
            ),
            judge_flags=["null_provider", "offline", "not_semantic"],
        )
        return LLMJudgeResult(
            case_id=judge_input.case_id,
            provider_name=self.config.provider_name,
            model_name=self.config.model_name,
            score=score,
            prompt_version=PROMPT_VERSION,
            raw_response=None,
        )


def run_llm_judge_for_cases(
    judge_inputs: Sequence[LLMJudgeInput],
    provider: BaseLLMJudgeProvider | None = None,
    config: LLMJudgeProviderConfig | None = None,
    *,
    input_source: str = "manual",
) -> LLMJudgeRunReport:
    """Run an optional judge provider over supplied cases and aggregate a report."""
    resolved_provider = provider or NullLLMJudgeProvider(config)
    max_cases = resolved_provider.config.max_cases
    selected_inputs = list(judge_inputs[:max_cases] if max_cases is not None else judge_inputs)
    results: list[LLMJudgeResult] = []
    for judge_input in selected_inputs:
        prompt = build_llm_judge_prompt(judge_input)
        results.append(resolved_provider.judge(judge_input, prompt))

    completed = sum(1 for result in results if result.status == "COMPLETED")
    skipped = sum(1 for result in results if result.status == "SKIPPED")
    errors = sum(1 for result in results if result.status == "ERROR")
    return LLMJudgeRunReport(
        generated_at=datetime.now(UTC).isoformat(),
        provider=resolved_provider.config,
        input_source=input_source,
        total_cases=len(selected_inputs),
        completed_cases=completed,
        skipped_cases=skipped,
        error_cases=errors,
        results=results,
        summary=_summarize_results(results),
        is_ci_gate=False,
    )


def _summarize_results(results: Sequence[LLMJudgeResult]) -> dict[str, float | int | str]:
    if not results:
        return {"mean_score": 0.0, "completed_cases": 0}
    fields = [
        "faithfulness_score",
        "answer_relevancy_score",
        "groundedness_score",
        "completeness_score",
        "uncertainty_honesty_score",
        "executive_usefulness_score",
        "judge_confidence",
    ]
    summary: dict[str, float | int | str] = {"completed_cases": len(results)}
    means: list[float] = []
    for field in fields:
        total = sum(float(getattr(result.score, field)) for result in results)
        value = round(total / len(results), 4)
        summary[f"mean_{field}"] = value
        if field != "judge_confidence":
            means.append(value)
    summary["mean_score"] = round(sum(means) / len(means), 4) if means else 0.0
    summary["status"] = "INFO"
    return summary
