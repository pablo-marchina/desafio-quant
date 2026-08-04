"""Prompt builders for the optional answer quality LLM judge."""

from __future__ import annotations

import json

from src.evaluation.llm_judge_schemas import LLMJudgeInput

PROMPT_VERSION = "optional-llm-judge-v1"

FAITHFULNESS_PROMPT = (
    "Faithfulness: judge whether the answer stays faithful to the supplied startup "
    "evidence, diagnosed gaps, recommendations, and RAG context. Penalize unsupported "
    "claims and invented facts."
)

ANSWER_RELEVANCY_PROMPT = (
    "Answer relevancy: judge whether the answer directly addresses the case context "
    "and the NVIDIA Startup AI Radar decision need."
)

GROUNDEDNESS_PROMPT = (
    "Groundedness: judge whether factual statements and NVIDIA recommendations are "
    "grounded in explicit evidence, RAG context, and a stated technical gap."
)

COMPLETENESS_PROMPT = (
    "Completeness: judge whether the answer covers the required executive sections, "
    "startup evidence, gaps, technologies, missing evidence, and next action."
)

UNCERTAINTY_HONESTY_PROMPT = (
    "Uncertainty honesty: judge whether the answer preserves uncertainty, weak "
    "evidence, low confidence, and missing evidence without overstating conclusions."
)

EXECUTIVE_USEFULNESS_PROMPT = (
    "Executive usefulness: judge whether the Action Brief is clear, concise, decision "
    "oriented, and useful for a human NVIDIA team reviewing the startup."
)

RUBRIC_PROMPTS = [
    FAITHFULNESS_PROMPT,
    ANSWER_RELEVANCY_PROMPT,
    GROUNDEDNESS_PROMPT,
    COMPLETENESS_PROMPT,
    UNCERTAINTY_HONESTY_PROMPT,
    EXECUTIVE_USEFULNESS_PROMPT,
]


def build_llm_judge_prompt(judge_input: LLMJudgeInput) -> str:
    """Build a complete judge prompt for one answer quality case."""
    context = {
        "case_id": judge_input.case_id,
        "case_description": judge_input.case_description,
        "pipeline_case_id": judge_input.pipeline_case_id,
        "startup_evidence": judge_input.startup_evidence,
        "rag_contexts": judge_input.rag_contexts,
        "diagnosed_gaps": judge_input.diagnosed_gaps,
        "nvidia_technology_candidates": judge_input.nvidia_technology_candidates,
        "recommendations": judge_input.recommendations,
        "missing_evidence": judge_input.missing_evidence,
        "uncertainties": judge_input.uncertainties,
        "deterministic_metrics": judge_input.deterministic_metrics,
    }
    return "\n".join(
        [
            "Optional LLM Judge for NVIDIA Startup AI Radar Answer Quality",
            f"Prompt version: {PROMPT_VERSION}",
            "",
            "Use only the supplied context. Separate fact, inference, and hypothesis. "
            "Do not create new startup claims or NVIDIA recommendations.",
            "",
            "## Context",
            json.dumps(context, indent=2, ensure_ascii=False, default=str),
            "",
            "## Answer",
            judge_input.answer_text,
            "",
            "## Evidence",
            json.dumps(judge_input.startup_evidence, indent=2, ensure_ascii=False, default=str),
            "",
            "## RAG Context",
            json.dumps(judge_input.rag_contexts, indent=2, ensure_ascii=False, default=str),
            "",
            "## Rubric",
            *[f"- {rubric}" for rubric in RUBRIC_PROMPTS],
            "",
            "Return JSON with scores from 0.0 to 1.0 for faithfulness_score, "
            "answer_relevancy_score, groundedness_score, completeness_score, "
            "uncertainty_honesty_score, executive_usefulness_score, judge_confidence, "
            "plus judge_rationale and judge_flags.",
        ]
    )
