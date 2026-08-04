from __future__ import annotations

import json
from pathlib import Path

from scripts.run_answer_quality_llm_judge import main as run_llm_judge_main
from src.evaluation.llm_judge_adapter import NullLLMJudgeProvider, run_llm_judge_for_cases
from src.evaluation.llm_judge_prompts import (
    ANSWER_RELEVANCY_PROMPT,
    COMPLETENESS_PROMPT,
    EXECUTIVE_USEFULNESS_PROMPT,
    FAITHFULNESS_PROMPT,
    GROUNDEDNESS_PROMPT,
    UNCERTAINTY_HONESTY_PROMPT,
    build_llm_judge_prompt,
)
from src.evaluation.llm_judge_schemas import LLMJudgeInput, LLMJudgeProviderConfig


def test_null_llm_judge_provider_runs_offline_with_predictable_scores() -> None:
    judge_input = _judge_input()
    provider = NullLLMJudgeProvider()

    first = provider.judge(judge_input, build_llm_judge_prompt(judge_input))
    second = provider.judge(judge_input, build_llm_judge_prompt(judge_input))

    assert first == second
    assert first.provider_name == "null"
    assert first.score.judge_confidence == 1.0
    assert first.score.faithfulness_score == 0.85
    assert "offline" in first.score.judge_flags


def test_run_llm_judge_for_cases_aggregates_info_report() -> None:
    report = run_llm_judge_for_cases(
        [_judge_input()],
        NullLLMJudgeProvider(LLMJudgeProviderConfig(provider_name="null", enabled=False)),
        input_source="unit-test",
    )

    assert report.is_ci_gate is False
    assert report.total_cases == 1
    assert report.completed_cases == 1
    assert report.summary["status"] == "INFO"
    assert report.summary["mean_faithfulness_score"] == 0.85


def test_prompt_contains_context_answer_evidence_and_rubric() -> None:
    prompt = build_llm_judge_prompt(_judge_input())

    assert "## Context" in prompt
    assert "## Answer" in prompt
    assert "## Evidence" in prompt
    assert "## RAG Context" in prompt
    assert "## Rubric" in prompt
    assert "Startup evidence claim" in prompt
    assert "Answer body" in prompt
    for rubric in (
        FAITHFULNESS_PROMPT,
        ANSWER_RELEVANCY_PROMPT,
        GROUNDEDNESS_PROMPT,
        COMPLETENESS_PROMPT,
        UNCERTAINTY_HONESTY_PROMPT,
        EXECUTIVE_USEFULNESS_PROMPT,
    ):
        assert rubric in prompt


def test_llm_judge_script_writes_json_and_markdown_offline(tmp_path: Path) -> None:
    json_path = tmp_path / "answer_quality_llm_judge_report.json"
    md_path = tmp_path / "answer_quality_llm_judge_report.md"

    exit_code = run_llm_judge_main(
        [
            "--max-cases",
            "1",
            "--output-json",
            str(json_path),
            "--output-md",
            str(md_path),
        ]
    )

    assert exit_code == 0
    data = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = md_path.read_text(encoding="utf-8")
    assert data["provider"]["provider_name"] == "null"
    assert data["is_ci_gate"] is False
    assert data["total_cases"] == 1
    assert "experimental, informational, and not a CI gate" in markdown


def _judge_input() -> LLMJudgeInput:
    return LLMJudgeInput(
        case_id="case-a",
        case_description="A case for optional judge testing.",
        pipeline_case_id="pipeline-a",
        answer_text="Answer body with a grounded NVIDIA recommendation.",
        startup_evidence=[{"claim": "Startup evidence claim", "source_url": "https://example.com"}],
        rag_contexts=[{"source_id": "nim", "content": "NVIDIA context"}],
        diagnosed_gaps=[{"gap": "high_latency", "detected": True}],
        nvidia_technology_candidates=[{"technology_name": "NVIDIA NIM"}],
        recommendations=[{"diagnosed_gap": "high_latency"}],
        missing_evidence=["Need benchmark data"],
        uncertainties=[{"description": "Latency claim is not benchmarked"}],
        deterministic_metrics={"answer_quality_status": "PASS"},
    )
